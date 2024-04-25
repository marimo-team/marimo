# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterator, Optional

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
    from marimo._ast.cell import CellId_t
    from marimo._messaging.types import Stream
    from marimo._runtime.runtime import Kernel
    from marimo._runtime.state import State


@dataclass
class KernelRuntimeContext(RuntimeContext):
    """Encapsulates runtime state for a session."""

    _kernel: Kernel
    _id_provider: Optional[IDProvider] = None

    @property
    def graph(self) -> DirectedGraph:
        return self._kernel.graph

    @property
    def execution_context(self) -> ExecutionContext | None:
        return self._kernel.execution_context

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
        try:
            self._id_provider = IDProvider(prefix)
            yield
        finally:
            self._id_provider = None

    def take_id(self) -> str:
        if self._id_provider is None:
            raise NoIDProviderException
        return self._id_provider.take_id()

    @property
    def globals(self) -> dict[str, Any]:
        return self._kernel.globals

    def get_ui_initial_value(self, object_id: str) -> Any:
        return self._kernel.get_ui_initial_value(object_id)

    def register_state_update(self, state: State[Any]) -> None:
        return self._kernel.register_state_update(state)


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
    from marimo._plugins.ui._core.registry import UIElementRegistry
    from marimo._runtime.virtual_file import VirtualFileRegistry

    runtime_context = KernelRuntimeContext(
        _kernel=kernel,
        ui_element_registry=UIElementRegistry(),
        function_registry=FunctionRegistry(),
        cell_lifecycle_registry=CellLifecycleRegistry(),
        virtual_file_registry=VirtualFileRegistry(),
        virtual_files_supported=virtual_files_supported,
        stream=stream,
        stdout=stdout,
        stderr=stderr,
    )
    initialize_context(runtime_context=runtime_context)
