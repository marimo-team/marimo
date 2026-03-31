# Copyright 2026 Marimo. All rights reserved.
"""Thread-local context for the runtime

Each client gets its own context.
"""

from __future__ import annotations

import abc
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from marimo._ast.app_config import _AppConfig
from marimo._messaging.context import HTTP_REQUEST_CTX
from marimo._runtime.cell_output_list import CellOutputList

if TYPE_CHECKING:
    from collections.abc import Iterator

    import duckdb

    from marimo._ast.app import (
        AppKernelRunnerRegistry,
        InternalApp,
    )
    from marimo._config.config import MarimoConfig
    from marimo._messaging.types import Stderr, Stdout, Stream
    from marimo._plugins.ui._core.registry import UIElementRegistry
    from marimo._runtime import dataflow
    from marimo._runtime.cell_lifecycle_registry import CellLifecycleRegistry
    from marimo._runtime.commands import HTTPRequest
    from marimo._runtime.functions import FunctionRegistry
    from marimo._runtime.params import CLIArgs, QueryParams
    from marimo._runtime.state import State, StateRegistry
    from marimo._runtime.virtual_file import VirtualFileRegistry
    from marimo._save.cache import CacheState
    from marimo._types.ids import CellId_t


class GlobalContext:
    """Context shared by all sessions."""

    def __init__(self) -> None:
        self._mpl_installed = False

    @property
    def mpl_installed(self) -> bool:
        """Whether matplotlib has been installed in this context."""
        return self._mpl_installed

    def set_mpl_installed(self, mpl_installed: bool) -> None:
        """Set whether matplotlib has been installed."""
        self._mpl_installed = mpl_installed


_GLOBAL_CONTEXT = GlobalContext()


def get_global_context() -> GlobalContext:
    """Return the singleton global context shared across all sessions."""
    return _GLOBAL_CONTEXT


@dataclass
class ExecutionContext:
    """Per-cell execution state, including the current cell ID and its outputs."""

    cell_id: CellId_t
    setting_element_value: bool
    # Cell ID corresponding to local graph object, and not prefixed in script
    # context.
    local_cell_id: Optional[CellId_t] = None
    # outputs set imperatively via mo.output.append and associated functions
    output: CellOutputList = field(default_factory=CellOutputList)
    duckdb_connection: duckdb.DuckDBPyConnection | None = None

    @contextmanager
    def with_connection(
        self, connection: duckdb.DuckDBPyConnection
    ) -> Iterator[None]:
        """Context manager to temporarily set the active DuckDB connection."""
        old_conn = self.duckdb_connection
        self.duckdb_connection = connection
        yield
        self.duckdb_connection = old_conn


@dataclass
class RuntimeContext(abc.ABC):
    """Abstract base class for a session's runtime context, holding all kernel-level state."""

    ui_element_registry: UIElementRegistry
    state_registry: StateRegistry
    function_registry: FunctionRegistry
    cell_lifecycle_registry: CellLifecycleRegistry
    virtual_file_registry: VirtualFileRegistry
    virtual_files_supported: bool
    app_kernel_runner_registry: AppKernelRunnerRegistry
    cache: CacheState
    # stream, stdout, stderr are _not_ owned by the context
    stream: Stream
    stdout: Stdout | None
    stderr: Stderr | None
    children: list[RuntimeContext]
    parent: RuntimeContext | None
    filename: str | None
    app_config: _AppConfig

    @property
    @abc.abstractmethod
    def graph(self) -> dataflow.DirectedGraph:
        """The notebook's reactive dataflow graph."""
        pass

    @property
    @abc.abstractmethod
    def globals(self) -> dict[str, Any]:
        """The kernel's global variable namespace."""
        pass

    @property
    @abc.abstractmethod
    def execution_context(self) -> ExecutionContext | None:
        """The execution context for the currently running cell, if any."""
        pass

    @property
    @abc.abstractmethod
    def marimo_config(self) -> MarimoConfig:
        """
        Get the marimo configuration.
        This is a merged configuration from the user config and project config.
        """
        pass

    @property
    def request(self) -> Optional[HTTPRequest]:
        """Get the current request context if any."""
        return HTTP_REQUEST_CTX.get(None)

    @property
    @abc.abstractmethod
    def cell_id(self) -> Optional[CellId_t]:
        """Get the cell id of the currently executing cell, if any."""
        pass

    @property
    @abc.abstractmethod
    def argv(self) -> list[str]:
        """The original argv the context was created with."""
        pass

    @property
    @abc.abstractmethod
    def cli_args(self) -> CLIArgs:
        """Get the CLI args."""
        pass

    @property
    @abc.abstractmethod
    def query_params(self) -> QueryParams:
        """Get the query params."""
        pass

    @abc.abstractmethod
    def get_ui_initial_value(self, object_id: str) -> Any:
        """Return the initial value for a UI element by its object ID."""
        pass

    @contextmanager
    @abc.abstractmethod
    def provide_ui_ids(self, prefix: str) -> Iterator[None]:
        """Context manager that scopes UI element ID generation under a prefix."""
        pass

    @abc.abstractmethod
    def take_id(self) -> str:
        """Take and return the next available UI element ID."""
        pass

    @abc.abstractmethod
    def register_state_update(self, state: State[Any]) -> None:
        """Register a state update to be processed after the current cell finishes."""
        pass

    @contextmanager
    @abc.abstractmethod
    def with_cell_id(self, cell_id: CellId_t) -> Iterator[None]:
        """Context manager that sets the currently executing cell ID."""
        pass

    def is_embedded(self) -> bool:
        """Return True if this context is embedded within a parent context."""
        return self.parent is not None

    def add_child(self, runtime_context: RuntimeContext) -> None:
        """Add a child runtime context (for embedded notebooks)."""
        if runtime_context not in self.children:
            self.children.append(runtime_context)

    def remove_child(self, runtime_context: RuntimeContext) -> None:
        """Remove a child runtime context and shut down its virtual file registry."""
        self.children.remove(runtime_context)
        runtime_context.virtual_file_registry.shutdown()
        assert runtime_context not in self.children

    @contextmanager
    def install(self) -> Iterator[None]:
        """Context manager that sets this as the thread-local runtime context."""
        global _THREAD_LOCAL_CONTEXT
        old_ctx = _THREAD_LOCAL_CONTEXT.runtime_context
        try:
            _THREAD_LOCAL_CONTEXT.runtime_context = self
            yield
        finally:
            _THREAD_LOCAL_CONTEXT.runtime_context = old_ctx

    @property
    @abc.abstractmethod
    def app(self) -> InternalApp:
        """The InternalApp this context is running."""
        pass


class _ThreadLocalContext(threading.local):
    """Thread-local container that holds thread/session-specific state."""

    def __init__(self) -> None:
        self.runtime_context: Optional[RuntimeContext] = None

    def initialize(self, runtime_context: RuntimeContext) -> None:
        self.runtime_context = runtime_context


class ContextNotInitializedError(Exception):
    """Raised when the runtime context has not been initialized for this thread."""


# Stores session-specific state, which is thread-local (relevant for run
# mode, in which every session runs in its own thread). Each thread
# must explicitly initialize this object.
_THREAD_LOCAL_CONTEXT = _ThreadLocalContext()


def initialize_context(runtime_context: RuntimeContext) -> None:
    """Initialize the thread-local runtime context; raises RuntimeError if already set."""
    try:
        get_context()
        raise RuntimeError("RuntimeContext was already initialized.")
    except ContextNotInitializedError:
        global _THREAD_LOCAL_CONTEXT
        _THREAD_LOCAL_CONTEXT.initialize(runtime_context=runtime_context)


def teardown_context() -> None:
    """Unset the context, for testing."""
    global _THREAD_LOCAL_CONTEXT
    _THREAD_LOCAL_CONTEXT.runtime_context = None


def get_context() -> RuntimeContext:
    """Return the runtime context.

    Throws a ContextNotInitializedError if the context has not been
    created.
    """
    if _THREAD_LOCAL_CONTEXT.runtime_context is None:
        raise ContextNotInitializedError
    return _THREAD_LOCAL_CONTEXT.runtime_context


def safe_get_context() -> Optional[RuntimeContext]:
    """Return the runtime context if it exists, otherwise None."""
    return _THREAD_LOCAL_CONTEXT.runtime_context


def runtime_context_installed() -> bool:
    """Return True if a runtime context has been installed in this thread."""
    try:
        get_context()
    except ContextNotInitializedError:
        return False
    else:
        return True
