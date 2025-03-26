# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Callable

from marimo._ast.cell import CellImpl
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.types import NoopStream
from marimo._runtime.app.common import RunOutput
from marimo._runtime.context.types import (
    get_context,
    runtime_context_installed,
    teardown_context,
)
from marimo._runtime.exceptions import (
    MarimoMissingRefError,
    MarimoRuntimeException,
)
from marimo._runtime.executor import (
    execute_cell,
    execute_cell_async,
)
from marimo._runtime.patches import (
    create_main_module,
    patch_main_module_context,
)
from marimo._runtime.runner.cell_runner import Runner
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._ast.app import InternalApp


class AppScriptRunner:
    """Runs an app in a script context."""

    def __init__(self, app: InternalApp, filename: str | None) -> None:
        self.app = app
        self.filename = filename

    async def _run_all(
        self,
        post_execute_hooks: list[Callable[[], Any]],
    ) -> RunOutput:
        with patch_main_module_context(
            create_main_module(
                file=self.filename, input_override=None, print_override=None
            )
        ) as module:
            roots = set(
                cid
                for cid in self.app.execution_order
                if cid in self.app.graph.cells
            )

            ctx = get_context()
            outputs: dict[CellId_t, Any] = {}

            def store_output(cell, runner, run_result):
                outputs[cell.cell_id] = run_result.output

            glbls = module.__dict__
            runner = Runner(
                roots=roots,
                graph=self.app.graph,
                glbls=glbls,
                execution_mode="autorun",
                execution_context=ctx.with_cell_id,
                post_execution_hooks=post_execute_hooks + [store_output],
                debugger=None,
            )
            await runner.run_all()
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

            outputs, defs = asyncio.run(
                self._run_all(
                    post_execute_hooks=post_execute_hooks,
                )
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
