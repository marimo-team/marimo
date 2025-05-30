# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from marimo._ast.app import AppKernelRunnerRegistry
from marimo._config.config import MarimoConfig
from marimo._messaging.types import Stderr, Stdout
from marimo._plugins.ui._core.ids import IDProvider, NoIDProviderException
from marimo._runtime.cell_lifecycle_registry import CellLifecycleRegistry
from marimo._runtime.context.types import (
    ExecutionContext,
    RuntimeContext,
    initialize_context,
)
from marimo._runtime.dataflow import DirectedGraph
from marimo._runtime.functions import FunctionRegistry
from marimo._runtime.params import CLIArgs, QueryParams
from marimo._server.model import SessionMode

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._ast.app import InternalApp
    from marimo._messaging.types import Stream
    from marimo._runtime.runtime import Kernel
    from marimo._runtime.state import State
    from marimo._types.ids import CellId_t


@dataclass
class KernelRuntimeContext(RuntimeContext):
    """Encapsulates runtime state for a session."""

    # The kernel is _not_ owned by the context; don't teardown.
    _kernel: Kernel
    _session_mode: SessionMode
    # app that owns this context; None for top-level contexts
    _app: Optional[InternalApp] = None
    _id_provider: Optional[IDProvider] = None
    _execution_context: Optional[ExecutionContext] = None

    @property
    def graph(self) -> DirectedGraph:
        return self._kernel.graph

    @property
    def globals(self) -> dict[str, Any]:
        return self._kernel.globals

    @property
    def execution_context(self) -> ExecutionContext | None:
        return self._execution_context

    @execution_context.setter
    def execution_context(
        self, execution_context: ExecutionContext | None
    ) -> None:
        self._execution_context = execution_context

    @property
    def marimo_config(self) -> MarimoConfig:
        return self._kernel.user_config

    @property
    def lazy(self) -> bool:
        return self._kernel.lazy()

    @property
    def cell_id(self) -> Optional[CellId_t]:
        """Get the cell id of the currently executing cell, if any."""
        if self.execution_context is not None:
            return self.execution_context.cell_id
        return None

    @property
    def cli_args(self) -> CLIArgs:
        """Get the CLI args."""
        return self._kernel.cli_args

    @property
    def argv(self) -> list[str]:
        """The original argv the kernel was created with."""
        return self._kernel.argv

    @property
    def query_params(self) -> QueryParams:
        """Get the query params."""
        return self._kernel.query_params

    @property
    def session_mode(self) -> SessionMode:
        """Get the session mode."""
        return self._session_mode

    @contextmanager
    def provide_ui_ids(self, prefix: str) -> Iterator[None]:
        old_id_provider = self._id_provider
        try:
            self._id_provider = IDProvider(prefix)
            yield
        finally:
            self._id_provider = old_id_provider

    def take_id(self) -> str:
        if self._id_provider is None:
            raise NoIDProviderException
        return self._id_provider.take_id()

    def get_ui_initial_value(self, object_id: str) -> Any:
        return self._kernel.get_ui_initial_value(object_id)

    def register_state_update(self, state: State[Any]) -> None:
        return self._kernel.register_state_update(state)

    @contextmanager
    def with_cell_id(self, cell_id: CellId_t) -> Iterator[None]:
        old = self.execution_context
        try:
            if old is not None:
                setting_element_value = old.setting_element_value
            else:
                setting_element_value = False
            self.execution_context = ExecutionContext(
                cell_id=cell_id,
                setting_element_value=setting_element_value,
            )
            yield
        finally:
            self.execution_context = old

    @property
    def app(self) -> InternalApp:
        assert self._app is not None
        return self._app


def create_kernel_context(
    *,
    kernel: Kernel,
    stream: Stream,
    stdout: Stdout | None,
    stderr: Stderr | None,
    virtual_files_supported: bool,
    mode: SessionMode,
    app: InternalApp | None = None,
    parent: KernelRuntimeContext | None = None,
) -> KernelRuntimeContext:
    from marimo._plugins.ui._core.registry import UIElementRegistry
    from marimo._runtime.state import StateRegistry
    from marimo._runtime.virtual_file import VirtualFileRegistry
    from marimo._save.stores import get_store

    return KernelRuntimeContext(
        _kernel=kernel,
        _session_mode=mode,
        _app=app,
        ui_element_registry=UIElementRegistry(),
        state_registry=StateRegistry(),
        function_registry=FunctionRegistry(),
        cache_store=get_store(kernel.app_metadata.filename),
        cell_lifecycle_registry=CellLifecycleRegistry(),
        app_kernel_runner_registry=AppKernelRunnerRegistry(),
        virtual_file_registry=VirtualFileRegistry(),
        virtual_files_supported=virtual_files_supported,
        stream=stream,
        stdout=stdout,
        stderr=stderr,
        children=[],
        parent=parent,
        filename=kernel.app_metadata.filename,
        app_config=kernel.app_metadata.app_config,
    )


def initialize_kernel_context(
    *,
    kernel: Kernel,
    stream: Stream,
    stdout: Stdout | None,
    stderr: Stderr | None,
    virtual_files_supported: bool,
    mode: SessionMode,
) -> KernelRuntimeContext:
    """Initializes thread-local/session-specific context.

    Must be called exactly once for each client thread.
    """
    ctx = create_kernel_context(
        kernel=kernel,
        stream=stream,
        stdout=stdout,
        stderr=stderr,
        virtual_files_supported=virtual_files_supported,
        mode=mode,
    )
    initialize_context(runtime_context=ctx)
    return ctx
