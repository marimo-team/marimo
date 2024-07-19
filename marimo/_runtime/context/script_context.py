# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterator, Optional

from marimo._cli.parse_args import args_from_argv
from marimo._plugins.ui._core.ids import NoIDProviderException
from marimo._plugins.ui._core.registry import UIElementRegistry
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
    from marimo._runtime.state import State


@dataclass
class ScriptRuntimeContext(RuntimeContext):
    """Encapsulates runtime state when running as a script."""

    _app: InternalApp

    def __post_init__(self) -> None:
        self._cli_args: CLIArgs | None = None
        self._query_params = QueryParams({})

    @property
    def graph(self) -> DirectedGraph:
        return self._app.graph

    @property
    def globals(self) -> dict[str, Any]:
        return {}

    @property
    def execution_context(self) -> ExecutionContext | None:
        return self._app.execution_context

    @property
    def cell_id(self) -> Optional[CellId_t]:
        """Get the cell id of the currently executing cell, if any."""
        if self.execution_context is not None:
            return self.execution_context.cell_id
        return None

    @property
    def cli_args(self) -> CLIArgs:
        """Get the CLI args."""
        if self._cli_args is None:
            self._cli_args = CLIArgs(args_from_argv())
        return self._cli_args

    @property
    def query_params(self) -> QueryParams:
        """Get the query params."""
        return self._query_params

    def get_ui_initial_value(self, object_id: str) -> Any:
        del object_id
        raise KeyError

    @contextmanager
    def provide_ui_ids(self, prefix: str) -> Iterator[None]:
        del prefix
        yield

    def take_id(self) -> str:
        raise NoIDProviderException

    def register_state_update(self, state: State[Any]) -> None:
        del state
        return

    @contextmanager
    def with_cell_id(self, cell_id: CellId_t) -> Iterator[None]:
        old = self.execution_context
        try:
            if old is not None:
                setting_element_value = old.setting_element_value
            else:
                setting_element_value = False
            self._app.set_execution_context(
                ExecutionContext(
                    cell_id=cell_id,
                    setting_element_value=setting_element_value,
                )
            )
            yield
        finally:
            self._app.set_execution_context(old)

    @property
    def app(self) -> InternalApp:
        return self._app


def initialize_script_context(app: InternalApp, stream: Stream) -> None:
    """Initializes thread-local/session-specific context.

    Must be called exactly once for each client thread.
    """
    from marimo._runtime.virtual_file import VirtualFileRegistry

    runtime_context = ScriptRuntimeContext(
        _app=app,
        ui_element_registry=UIElementRegistry(),
        function_registry=FunctionRegistry(),
        cell_lifecycle_registry=CellLifecycleRegistry(),
        virtual_file_registry=VirtualFileRegistry(),
        virtual_files_supported=False,
        stream=stream,
        stdout=None,
        stderr=None,
        children=[],
        parent=None,
    )
    initialize_context(runtime_context=runtime_context)
