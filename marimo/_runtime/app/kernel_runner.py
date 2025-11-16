# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import types
import weakref
from typing import TYPE_CHECKING, Any

from marimo._ast.cell import CellImpl
from marimo._config.config import DEFAULT_CONFIG
from marimo._runtime.app.common import RunOutput
from marimo._runtime.context.types import get_context
from marimo._runtime.patches import create_main_module
from marimo._runtime.requests import (
    AppMetadata,
    ExecutionRequest,
    FunctionCallRequest,
    SetUIElementValueRequest,
)
from marimo._runtime.runner import cell_runner
from marimo._server.model import SessionMode
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._ast.app import InternalApp
    from marimo._messaging.ops import HumanReadableStatus
    from marimo._plugins.core.web_component import JSONType


class AppKernelRunner:
    """Runs an app in a kernel context; used for composition."""

    def __init__(self, app: InternalApp) -> None:
        from marimo._runtime.context.kernel_context import (
            KernelRuntimeContext,
            create_kernel_context,
        )
        from marimo._runtime.runner.hooks_post_execution import (
            _reset_matplotlib_context,
        )
        from marimo._runtime.runtime import Kernel

        self.app = app
        self._outputs: dict[CellId_t, Any] = {}

        ctx = get_context()
        if not isinstance(ctx, KernelRuntimeContext):
            raise RuntimeError("AppKernelRunner requires a kernel context.")

        def cache_output(
            cell: CellImpl,
            runner: cell_runner.Runner,
            run_result: cell_runner.RunResult,
        ) -> None:
            """Update the app's cached outputs."""
            from marimo._plugins.stateless.flex import vstack

            del runner
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
            post_execution_hooks=[cache_output, _reset_matplotlib_context],
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

        # Parent->child exposures: namespace and current values. This registry lets
        # us compare parent updates and avoid re-running child cells when values do
        # actually change.
        self._exposed_values: dict[str, Any] | None = None
        self._exposed_namespace: str | None = None
        self._exposed_readonly: bool = True

    @property
    def outputs(self) -> dict[CellId_t, Any]:
        return self._outputs

    @property
    def globals(self) -> dict[str, Any]:
        return self._kernel.globals

    # Simple read-only proxy that can be mutated behind the scenes.
    class _ReadOnlyNamespace:
        """
        A read-only, attribute-style namespace object exposed to child code.
        The runner mutates the backing dictionary so child reads fresh values,
        while the user code in the child cannot assign to attributes.
        """

        __slots__ = ("_data",)

        def __init__(self, data: dict[str, Any]) -> None:
            object.__setattr__(self, "_data", data)

        def __getattr__(self, k: str) -> Any:
            try:
                return self._data[k]
            except KeyError as e:
                raise AttributeError(k) from e

        def __setattr__(self, k: str, v: Any) -> None:
            raise AttributeError("read-only namespace")

        def __getitem__(self, k: str) -> Any:
            return self._data[k]

        def __iter__(self):
            return iter(self.data)

        def __dir__(self):
            return dir(self.data.keys())

    @property
    def exposed_namespace(self) -> str | None:
        """Name of the namespace injected into child globals (e.g., `parent`), or
        None if flat injection was used."""
        return self._exposed_namespace

    def register_exposed_bindings(
        self,
        *,
        expose: dict[str, Any] | Mapping[str, Any],
        namespace: str | None,
        readonly: bool = True,
    ) -> None:
        """Install parent->child exposures into the child kernel.

        - If `namespace` is provided (recommended), a read-only proxy is bound at
          `globals()[namespace]` in the child. Child code should reference the name
          **statically** to be tracked by the analyzer.
        - If `namespace` is None, names are injected flat. Advanced and subject to
          shadowing by child code!
        """
        # Normalize to a mutable dictionary we own
        values = dict(expose)
        self._exposed_values = values
        self._exposed_namespace = namespace
        self._exposed_readonly = readonly

        if namespace:
            ns_obj = (
                self._ReadOnlyNamespace(values)
                if readonly
                else types.SimpleNamespace(**values)  # type: ignore[name-defined]
            )
            # Bind child into globals
            self._kernel.globals[namespace] = ns_obj
        else:
            # Flat injection: advanced, cannot fully prevent shadowing
            for k, v in values.items():
                self._kernel.globals[k] = v

    def apply_exposed_binding_updates(
        self, updates: dict[str, Any]
    ) -> set[str]:
        """
        Update child namespace with new values and return the set of names that actually changed.

        Used to compute a minimal re-run set.
        """
        if self._exposed_values is None:
            return set()
        changed: set[str] = set()
        for k, v in updates.items():
            if k not in self._exposed_values:
                continue
            old = self._exposed_values.get(k, object())
            if old is v or old == v:
                continue
            self._exposed_values[k] = v
            changed.add(k)
        # If namespaced, the proxy reads from _exposed_values so no extra work is needed
        # If flat, also refresh direct globals to keep reads consistent
        if changed and not self._exposed_namespace:
            for k in changed:
                self._kernel.globals[k] = self._exposed_values[k]
        return changed

    async def run(self, cells_to_run: set[CellId_t]) -> RunOutput:
        execution_requests = [
            ExecutionRequest(cell_id=cid, code=cell._cell.code, request=None)
            for cid in cells_to_run
            if (cell := self.app.cell_manager.cell_data_at(cid).cell)
            is not None
        ]

        with self._runtime_context.install():
            await self._kernel.run(execution_requests)
        return self.outputs, self._kernel.globals

    async def set_ui_element_value(
        self, request: SetUIElementValueRequest
    ) -> bool:
        with self._runtime_context.install():
            return await self._kernel.set_ui_element_value(request)

    async def function_call(
        self, request: FunctionCallRequest
    ) -> tuple[HumanReadableStatus, JSONType, bool]:
        with self._runtime_context.install():
            return await self._kernel.function_call_request(request)
