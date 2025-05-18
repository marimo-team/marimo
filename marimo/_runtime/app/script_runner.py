# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Callable, Optional

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
)
from marimo._runtime.executor import (
    ExecutionConfig,
    get_executor,
)
from marimo._runtime.patches import (
    create_main_module,
    patch_main_module_context,
)
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from marimo._ast.app import InternalApp


class AppScriptRunner:
    """Runs an app in a script context."""

    def __init__(
        self,
        app: InternalApp,
        filename: str | None,
        glbls: Optional[dict[str, Any]] = None,
    ) -> None:
        self.app = app
        self.filename = filename
        self.cells_cancelled: set[CellId_t] = set()
        self._glbls = glbls if glbls else {}
        self.cells_to_run = [
            cid
            for cid in self.app.execution_order
            if app.cell_manager.cell_data_at(cid).cell is not None
            and not self.app.graph.is_disabled(cid)
        ]
        self._executor = get_executor(ExecutionConfig())

    def _cancel(self, cell_id: CellId_t) -> None:
        cancelled = set(
            cid
            for cid in dataflow.transitive_closure(
                self.app.graph, set([cell_id])
            )
            if cid in self.cells_to_run
        )
        for cid in cancelled:
            self.app.graph.cells[cid].set_run_result_status("cancelled")
        self.cells_cancelled |= cancelled

    def _run_synchronous(
        self,
        post_execute_hooks: list[Callable[[], Any]],
    ) -> RunOutput:
        with patch_main_module_context(
            create_main_module(
                file=self.filename, input_override=None, print_override=None
            )
        ) as module:
            glbls = module.__dict__
            glbls.update(self._glbls)
            outputs: dict[CellId_t, Any] = {}
            while self.cells_to_run:
                cid = self.cells_to_run.pop(0)
                if cid in self.cells_cancelled:
                    continue
                # Set up has already run in this case.
                if cid == CellId_t(SETUP_CELL_NAME):
                    for hook in post_execute_hooks:
                        hook()
                    continue

                cell = self.app.graph.cells[cid]
                with get_context().with_cell_id(cid):
                    try:
                        output = self._executor.execute_cell(
                            cell, glbls, self.app.graph
                        )
                        outputs[cid] = output
                    except MarimoRuntimeException as e:
                        unwrapped_exception: BaseException | None = e.__cause__

                        if isinstance(unwrapped_exception, MarimoStopError):
                            self._cancel(cid)
                        else:
                            raise e
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
                file=self.filename, input_override=None, print_override=None
            )
        ) as module:
            glbls = module.__dict__
            glbls.update(self._glbls)
            outputs: dict[CellId_t, Any] = {}

            while self.cells_to_run:
                cid = self.cells_to_run.pop(0)
                if cid in self.cells_cancelled:
                    continue

                if cid == CellId_t(SETUP_CELL_NAME):
                    for hook in post_execute_hooks:
                        hook()
                    continue

                cell = self.app.graph.cells[cid]
                with get_context().with_cell_id(cid):
                    try:
                        output = await self._executor.execute_cell_async(
                            cell, glbls, self.app.graph
                        )
                        outputs[cid] = output
                    except MarimoRuntimeException as e:
                        unwrapped_exception: BaseException | None = e.__cause__

                        if isinstance(unwrapped_exception, MarimoStopError):
                            self._cancel(cid)
                        else:
                            raise e
                    finally:
                        for hook in post_execute_hooks:
                            hook()
        return outputs, glbls

    def run(self) -> RunOutput:
        from marimo._runtime.context.script_context import (
            initialize_script_context,
        )

        app = self.app

        is_async = False
        for cell in app.cell_manager.cells():
            if cell is None:
                raise RuntimeError(
                    "Unparsable cell encountered. This is a bug in marimo, "
                    "please raise an issue."
                )

            if cell._is_coroutine:
                is_async = True
                break

        installed_script_context = False
        try:
            if not runtime_context_installed():
                # script context is ephemeral, only installed while the app is
                # running
                initialize_script_context(
                    app=app, stream=NoopStream(), filename=self.filename
                )
                installed_script_context = True

            # formatters aren't automatically registered when running as a
            # script
            from marimo._output.formatters.formatters import (
                register_formatters,
            )
            from marimo._output.formatting import FORMATTERS

            if not FORMATTERS:
                register_formatters()

            post_execute_hooks = []
            if DependencyManager.matplotlib.has():
                from marimo._output.mpl import close_figures

                post_execute_hooks.append(close_figures)

            if is_async:
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

        # Cell runner manages the exception handling for kernel
        # runner, but script runner should raise the wrapped
        # exception if invoked directly.
        except MarimoRuntimeException as e:
            # MarimoMissingRefError, wraps the under lying NameError
            # for context, so we raise the NameError directly.
            if isinstance(e.__cause__, MarimoMissingRefError):
                # For type checking + sanity check
                if not isinstance(e.__cause__.name_error, NameError):
                    raise MarimoRuntimeException(
                        "Unexpected error occurred while running the app. "
                        "Improperly wrapped MarimoMissingRefError exception. "
                        "Please report this issue to "
                        "https://github.com/marimo-team/marimo/issues"
                    ) from e.__cause__
                raise e.__cause__.name_error from e.__cause__
            # For all other exceptions, we raise the wrapped exception
            # from "None" to indicate this is an Error propagation, and to not
            # muddy the stacktrace from the failing cells themselves.
            raise e.__cause__ from None  # type: ignore
        finally:
            if installed_script_context:
                teardown_context()
