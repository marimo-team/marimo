# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterator, Optional

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

if TYPE_CHECKING:
    from marimo._ast.app import InternalApp
    from marimo._ast.cell import CellId_t
    from marimo._messaging.types import Stream
    from marimo._runtime.runtime import Kernel
    from marimo._runtime.state import State


@dataclass
class KernelRuntimeContext(RuntimeContext):
    """Encapsulates runtime state for a session."""

    _kernel: Kernel
    # app that owns this context; None for top-level contexts
    _app: Optional[InternalApp] = None
    _id_provider: Optional[IDProvider] = None

    @property
    def graph(self) -> DirectedGraph:
        return self._kernel.graph

    @property
    def globals(self) -> dict[str, Any]:
        return self._kernel.globals

    @property
    def execution_context(self) -> ExecutionContext | None:
        return self._kernel.execution_context

    @property
    def user_config(self) -> MarimoConfig:
        return self._kernel.user_config

    @property
    def lazy(self) -> bool:
        return self._kernel.lazy()

    @property
    def cell_id(self) -> Optional[CellId_t]:
        """Get the cell id of the currently executing cell, if any."""
        if self._kernel.execution_context is not None:
            return self._kernel.execution_context.cell_id
        return None

    @property
    def cli_args(self) -> CLIArgs:
        """Get the CLI args."""
        return self._kernel.cli_args

    @property
    def query_params(self) -> QueryParams:
        """Get the query params."""
        return self._kernel.query_params

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
            self._kernel.execution_context = ExecutionContext(
                cell_id=cell_id,
                setting_element_value=setting_element_value,
            )
            yield
        finally:
            self._kernel.execution_context = old

    @property
    def app(self) -> InternalApp:
        assert self._app is not None
        return self._app


def create_kernel_context(
    kernel: Kernel,
    stream: Stream,
    stdout: Stdout | None,
    stderr: Stderr | None,
    virtual_files_supported: bool = True,
    app: InternalApp | None = None,
    parent: KernelRuntimeContext | None = None,
) -> KernelRuntimeContext:
    from marimo._plugins.ui._core.registry import UIElementRegistry
    from marimo._runtime.state import StateRegistry
    from marimo._runtime.virtual_file import VirtualFileRegistry

    return KernelRuntimeContext(
        _kernel=kernel,
        _app=app,
        ui_element_registry=UIElementRegistry(),
        state_registry=StateRegistry(),
        function_registry=FunctionRegistry(),
        cell_lifecycle_registry=CellLifecycleRegistry(),
        virtual_file_registry=VirtualFileRegistry(),
        virtual_files_supported=virtual_files_supported,
        stream=stream,
        stdout=stdout,
        stderr=stderr,
        children=[],
        parent=parent,
        filename=kernel.app_metadata.filename,
    )


def initialize_kernel_context(
    kernel: Kernel,
    stream: Stream,
    stdout: Stdout | None,
    stderr: Stderr | None,
    virtual_files_supported: bool = True,
) -> None:
    """Initializes thread-local/session-specific context.

    Must be called exactly once for each client thread.
    """
    initialize_context(
        runtime_context=create_kernel_context(
            kernel, stream, stdout, stderr, virtual_files_supported
        )
    )
