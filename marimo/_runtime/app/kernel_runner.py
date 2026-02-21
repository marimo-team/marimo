# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Any

from marimo._ast.cell import CellImpl
from marimo._config.config import DEFAULT_CONFIG
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.app.common import RunOutput
from marimo._runtime.commands import (
    AppMetadata,
    ExecuteCellCommand,
    InvokeFunctionCommand,
    UpdateUIElementCommand,
)
from marimo._runtime.context.types import get_context
from marimo._runtime.patches import create_main_module
from marimo._runtime.runner import cell_runner, hook_context
from marimo._session.model import SessionMode
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from marimo._ast.app import InternalApp
    from marimo._messaging.notification import HumanReadableStatus
    from marimo._plugins.core.web_component import JSONType


def _defs_equal(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    """Safely compare embed defs, handling NumPy arrays without ambiguous truth values."""

    if a is b:
        return True
    if a is None or b is None:
        return False
    if a.keys() != b.keys():
        return False

    for key in a:
        va, vb = a[key], b[key]

        # identical object
        if va is vb:
            continue

        try:
            if DependencyManager.numpy.imported():
                import numpy as np

                if isinstance(va, np.ndarray) and isinstance(vb, np.ndarray):
                    if not np.array_equal(va, vb):
                        return False
                    continue

            if va != vb:
                return False

        except Exception:
            # Any ambiguous or unsafe comparison => treat as changed
            return False

    return True


class AppKernelRunner:
    """Runs an app in a kernel context; used for composition."""

    def __init__(self, app: InternalApp) -> None:
        from marimo._runtime.context.kernel_context import (
            KernelRuntimeContext,
            create_kernel_context,
        )
        from marimo._runtime.runner.hooks import NotebookCellHooks
        from marimo._runtime.runner.hooks_post_execution import (
            _reset_matplotlib_context,
        )
        from marimo._runtime.runtime import Kernel

        self.app = app
        self._outputs: dict[CellId_t, Any] = {}
        self._previously_seen_defs: dict[str, Any] | None = None

        ctx = get_context()
        if not isinstance(ctx, KernelRuntimeContext):
            raise RuntimeError("AppKernelRunner requires a kernel context.")  # noqa: TRY004

        def cache_output(
            cell: CellImpl,
            ctx: hook_context.PostExecutionHookContext,
            run_result: cell_runner.RunResult,
        ) -> None:
            """Update the app's cached outputs."""
            from marimo._plugins.stateless.flex import vstack

            del ctx
            if (
                run_result.output is None
                and run_result.accumulated_output is not None
            ):
                self.outputs[cell.cell_id] = vstack(
                    run_result.accumulated_output
                )
            else:
                self.outputs[cell.cell_id] = run_result.output

        filename = app.filename if app.filename is not None else "<unknown>"

        # Create minimal hooks for embedded app execution
        hooks = NotebookCellHooks()
        hooks.add_post_execution(cache_output)
        hooks.add_post_execution(_reset_matplotlib_context)

        self._kernel = Kernel(
            cell_configs={},
            app_metadata=AppMetadata(
                {},
                ctx.cli_args.to_dict(),
                argv=ctx.argv,
                filename=filename,
                app_config=app.config,
            ),
            stream=ctx.stream,
            stdout=None,
            stderr=None,
            stdin=None,
            module=create_main_module(
                filename, input_override=None, print_override=None
            ),
            user_config=DEFAULT_CONFIG,
            enqueue_control_request=lambda _: None,
            hooks=hooks,
        )

        # We push a new runtime context onto the "stack", corresponding to this
        # app. The context is removed when the app object is destroyed.
        self._runtime_context = create_kernel_context(
            kernel=self._kernel,
            app=app,
            stream=ctx.stream,
            stdout=None,
            stderr=None,
            virtual_files_supported=True,
            mode=SessionMode.EDIT,
            parent=ctx,
        )
        ctx.add_child(self._runtime_context)
        finalizer = weakref.finalize(
            self, ctx.remove_child, self._runtime_context
        )
        finalizer.atexit = False

        # Register cells through the kernel runner, so that compilation only
        # occurs once.
        for cell_id, cell in app.cell_manager.valid_cells():
            self._kernel._register_cell(cell_id, cell._cell, stale=False)

    @property
    def outputs(self) -> dict[CellId_t, Any]:
        return self._outputs

    def are_outputs_cached(self, defs: dict[str, Any] | None) -> bool:
        # The equality check is brittle but hashing isn't great either ...
        return (
            _defs_equal(defs, self._previously_seen_defs)
            and len(self.outputs) > 0
        )

    def register_defs(self, defs: dict[str, Any] | None) -> None:
        self._previously_seen_defs = defs

    @property
    def globals(self) -> dict[str, Any]:
        return self._kernel.globals

    async def run(self, cells_to_run: set[CellId_t]) -> RunOutput:
        execution_requests = [
            ExecuteCellCommand(cell_id=cid, code=cell._cell.code, request=None)
            for cid in cells_to_run
            if (cell := self.app.cell_manager.cell_data_at(cid).cell)
            is not None
        ]

        execution_mode = self._kernel.reactive_execution_mode
        try:
            graph = self._kernel.graph
            # The _only_ cells that run should be the ones in
            # cells_to_run. For this reason we set the execution
            # mode to lazy. We also make all cells stale to ensure
            # that ancestors aren't run.
            for c in graph.cells.values():
                c.set_stale(stale=False, broadcast=False)
            self._kernel.reactive_execution_mode = "lazy"
            with self._runtime_context.install():
                await self._kernel.run(execution_requests)
        finally:
            self._kernel.reactive_execution_mode = execution_mode

        return self.outputs, self._kernel.globals

    async def set_ui_element_value(
        self, request: UpdateUIElementCommand
    ) -> bool:
        with self._runtime_context.install():
            return await self._kernel.set_ui_element_value(request)

    async def function_call(
        self, request: InvokeFunctionCommand
    ) -> tuple[HumanReadableStatus, JSONType, bool]:
        with self._runtime_context.install():
            return await self._kernel.function_call_request(request)
