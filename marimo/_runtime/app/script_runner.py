# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from marimo._ast.names import SETUP_CELL_NAME
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.types import NoopStream
from marimo._runtime import dataflow
from marimo._runtime.app.common import RunOutput
from marimo._runtime.context.types import (
    get_context,
    runtime_context_installed,
    teardown_context,
)
from marimo._runtime.control_flow import MarimoStopError
from marimo._runtime.exceptions import (
    MarimoMissingRefError,
    MarimoRuntimeException,
    unwrap_user_exception,
)
from marimo._runtime.executor import (
    Evaluator,
    resolve_executor,
)
from marimo._runtime.patches import (
    create_main_module,
    extract_docstring_from_header,
    patch_main_module_context,
)
from marimo._runtime.runner.result import RunResult
from marimo._runtime.runner.scheduler import SequentialScheduler
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._ast.app import InternalApp


class AppScriptRunner:
    """Runs an app in a script context."""

    def __init__(
        self,
        app: InternalApp,
        filename: str | None,
        glbls: dict[str, Any] | None = None,
    ) -> None:
        self.app = app
        self.filename = filename
        self._docstring = extract_docstring_from_header(app._app._header)
        self._glbls = glbls if glbls else {}

        # Setup cell cannot be overridden, and it's possible that some
        # variables are not defined, so ignore it.
        pruned_execution_order = dataflow.prune_cells_for_overrides(
            self.app.graph,
            self.app.execution_order,
            self._glbls,
            excluded=CellId_t(SETUP_CELL_NAME),
        )

        cells_to_run = [
            cid
            for cid in pruned_execution_order
            if app.cell_manager.cell_data_at(cid).cell is not None
            and not self.app.graph.is_disabled(cid)
        ]

        self._scheduler = SequentialScheduler(cells_to_run, self.app.graph)
        self._evaluator = Evaluator(executor=resolve_executor(), lifecycles=[])

    def _is_async(self) -> bool:
        app = self.app
        for cell in app.cell_manager.cells():
            if cell is None:
                raise RuntimeError(
                    "Unparsable cell encountered. This is a bug in marimo, "
                    "please raise an issue."
                )

            if cell._is_coroutine:
                return True
        return False

    def _get_post_execute_hooks(self) -> list[Callable[[], Any]]:
        post_execute_hooks: list[Callable[[], Any]] = []
        if DependencyManager.matplotlib.has():
            from marimo._output.mpl import close_figures

            post_execute_hooks.append(close_figures)
        return post_execute_hooks

    def _initialize_runtime_context(self) -> bool:
        from marimo._runtime.context.script_context import (
            initialize_script_context,
        )

        if runtime_context_installed():
            return False

        # script context is ephemeral, only installed while the app is
        # running
        initialize_script_context(
            app=self.app, stream=NoopStream(), filename=self.filename
        )
        return True

    def _register_formatters(self) -> None:
        # formatters aren't automatically registered when running as a
        # script
        from marimo._output.formatters.formatters import (
            register_formatters,
        )
        from marimo._output.formatting import FORMATTERS

        if not FORMATTERS.is_empty():
            from marimo._runtime.context import get_context

            register_formatters(
                theme=get_context().marimo_config["display"]["theme"]
            )

    # _run_synchronous and _run_asynchronous are deliberate near-twins:
    # the only difference is the await on the cell step. Keeping them
    # as separate methods (rather than wrapping with asyncio.run
    # unconditionally) preserves the no-event-loop guarantee for purely
    # synchronous apps.
    def _run_synchronous(
        self,
        post_execute_hooks: list[Callable[[], Any]],
    ) -> RunOutput:
        with patch_main_module_context(
            create_main_module(
                file=self.filename,
                input_override=None,
                print_override=None,
                doc=self._docstring,
            )
        ) as module:
            glbls = module.__dict__
            glbls.update(self._glbls)

            outputs: dict[CellId_t, Any] = {}
            while self._scheduler.pending():
                cid = self._scheduler.pop_cell()
                if self._scheduler.cancelled(cid):
                    continue
                # Setup has already run by this point.
                if cid == CellId_t(SETUP_CELL_NAME):
                    for hook in post_execute_hooks:
                        hook()
                    continue
                cell = self.app.graph.cells[cid]
                with get_context().with_cell_id(cid):
                    try:
                        result = self._evaluator.evaluate_sync(cell, glbls)
                        self._handle_run_result(cid, result, outputs)
                    finally:
                        for hook in post_execute_hooks:
                            hook()
        return outputs, glbls

    async def _run_asynchronous(
        self,
        post_execute_hooks: list[Callable[[], Any]],
    ) -> RunOutput:
        with patch_main_module_context(
            create_main_module(
                file=self.filename,
                input_override=None,
                print_override=None,
                doc=self._docstring,
            )
        ) as module:
            glbls = module.__dict__
            glbls.update(self._glbls)

            outputs: dict[CellId_t, Any] = {}
            while self._scheduler.pending():
                cid = self._scheduler.pop_cell()
                if self._scheduler.cancelled(cid):
                    continue
                # Setup has already run by this point.
                if cid == CellId_t(SETUP_CELL_NAME):
                    for hook in post_execute_hooks:
                        hook()
                    continue
                cell = self.app.graph.cells[cid]
                with get_context().with_cell_id(cid):
                    try:
                        result = await self._evaluator.evaluate(cell, glbls)
                        self._handle_run_result(cid, result, outputs)
                    finally:
                        for hook in post_execute_hooks:
                            hook()
        return outputs, glbls

    def _handle_run_result(
        self,
        cid: CellId_t,
        result: RunResult,
        outputs: dict[CellId_t, Any],
    ) -> None:
        """Classify the Evaluator's RunResult; record output/cancel/raise."""
        exc = result.exception
        if exc is None:
            outputs[cid] = result.output
            return
        if not isinstance(exc, BaseException):
            # Defensive check descendants, since all exceptions are expected to
            # be wrapper..
            outputs[cid] = result.output
            self._scheduler.cancel(cid)
            return
        if isinstance(exc, MarimoRuntimeException):
            unwrapped = unwrap_user_exception(exc, self.app.graph)
            if isinstance(unwrapped, MarimoStopError):
                outputs[cid] = unwrapped.output
                self._scheduler.cancel(cid)
                return
            if isinstance(unwrapped, MarimoMissingRefError):
                name_err = unwrapped.name_error
                raise (
                    name_err if name_err is not None else unwrapped
                ) from None
        raise exc

    def run(self) -> RunOutput:
        installed_script_context = False
        try:
            installed_script_context = self._initialize_runtime_context()
            self._register_formatters()
            post_execute_hooks = self._get_post_execute_hooks()

            if self._is_async():
                outputs, defs = asyncio.run(
                    self._run_asynchronous(
                        post_execute_hooks=post_execute_hooks,
                    )
                )
            else:
                outputs, defs = self._run_synchronous(
                    post_execute_hooks=post_execute_hooks,
                )
            return outputs, defs

        # Raise the wrapped user exception from "None" so the stack
        # trace points at the failing cell, not the runner.
        except MarimoRuntimeException as e:
            raise e.__cause__ from None  # type: ignore
        finally:
            if installed_script_context:
                teardown_context()

    async def run_async(self) -> RunOutput:
        installed_script_context = False
        try:
            installed_script_context = self._initialize_runtime_context()
            self._register_formatters()
            post_execute_hooks = self._get_post_execute_hooks()

            if self._is_async():
                outputs, defs = await self._run_asynchronous(
                    post_execute_hooks=post_execute_hooks,
                )
            else:
                outputs, defs = self._run_synchronous(
                    post_execute_hooks=post_execute_hooks,
                )
            return outputs, defs

        # Raise the wrapped user exception from "None" so the stack
        # trace points at the failing cell, not the runner.
        except MarimoRuntimeException as e:
            raise e.__cause__ from None  # type: ignore
        finally:
            if installed_script_context:
                teardown_context()
