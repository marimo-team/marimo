# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Callable, Iterator

from marimo._ast.cell import CellId_t, CellImpl
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.types import NoopStream
from marimo._runtime.app.common import RunOutput
from marimo._runtime.context.types import (
    get_context,
    runtime_context_installed,
    teardown_context,
)
from marimo._runtime.executor import (
    MarimoMissingRefError,
    MarimoRuntimeException,
    execute_cell,
    execute_cell_async,
)
from marimo._runtime.patches import (
    create_main_module,
    patch_main_module_context,
)

if TYPE_CHECKING:
    from marimo._ast.app import InternalApp


class AppScriptRunner:
    """Runs an app in a script context."""

    def __init__(self, app: InternalApp) -> None:
        self.app = app

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

            if cell._is_coroutine():
                is_async = True
                break

        installed_script_context = False
        try:
            if not runtime_context_installed():
                # script context is ephemeral, only installed while the app is
                # running
                initialize_script_context(app=app, stream=NoopStream())
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
            if DependencyManager.has_matplotlib():
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

    def _cell_iterator(self) -> Iterator[CellImpl]:
        app = self.app
        for cid in app.execution_order:
            cell = app.cell_manager.cell_data_at(cid).cell
            if cell is None:
                continue

            if cell is not None and not app.graph.is_disabled(cid):
                yield cell._cell

    def _run_synchronous(
        self,
        post_execute_hooks: list[Callable[[], Any]],
    ) -> RunOutput:
        with patch_main_module_context(
            create_main_module(file=None, input_override=None)
        ) as module:
            glbls = module.__dict__
            outputs: dict[CellId_t, Any] = {}
            for cell in self._cell_iterator():
                with get_context().with_cell_id(cell.cell_id):
                    output = execute_cell(cell, glbls, self.app.graph)
                    for hook in post_execute_hooks:
                        hook()
                outputs[cell.cell_id] = output
        return outputs, glbls

    async def _run_asynchronous(
        self,
        post_execute_hooks: list[Callable[[], Any]],
    ) -> RunOutput:
        with patch_main_module_context(
            create_main_module(file=None, input_override=None)
        ) as module:
            glbls = module.__dict__
            outputs: dict[CellId_t, Any] = {}
            for cell in self._cell_iterator():
                with get_context().with_cell_id(cell.cell_id):
                    output = await execute_cell_async(
                        cell, glbls, self.app.graph
                    )
                    for hook in post_execute_hooks:
                        hook()
                outputs[cell.cell_id] = output
        return outputs, glbls
