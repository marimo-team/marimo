# Copyright 2024 Marimo. All rights reserved.
"""Thread-local context for the runtime

Each client gets its own context.
"""

from __future__ import annotations

import abc
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterator, Optional

from marimo._config.config import MarimoConfig
from marimo._messaging.types import Stderr, Stdout
from marimo._runtime import dataflow
from marimo._runtime.cell_lifecycle_registry import CellLifecycleRegistry
from marimo._runtime.functions import FunctionRegistry

if TYPE_CHECKING:
    from marimo._ast.app import InternalApp
    from marimo._ast.cell import CellId_t
    from marimo._messaging.types import Stream
    from marimo._output.hypertext import Html
    from marimo._plugins.ui._core.registry import UIElementRegistry
    from marimo._runtime.params import CLIArgs, QueryParams
    from marimo._runtime.state import State
    from marimo._runtime.virtual_file import VirtualFileRegistry


class GlobalContext:
    """Context shared by all sessions."""

    def __init__(self) -> None:
        self._mpl_installed = False

    @property
    def mpl_installed(self) -> bool:
        return self._mpl_installed

    def set_mpl_installed(self, mpl_installed: bool) -> None:
        self._mpl_installed = mpl_installed


_GLOBAL_CONTEXT = GlobalContext()


def get_global_context() -> GlobalContext:
    return _GLOBAL_CONTEXT


@dataclass
class ExecutionContext:
    cell_id: CellId_t
    setting_element_value: bool
    # Cell ID corresponding to local graph object, and not prefixed in script
    # context.
    local_cell_id: Optional[CellId_t] = None
    # output object set imperatively
    output: Optional[list[Html]] = None


@dataclass
class RuntimeContext(abc.ABC):
    ui_element_registry: UIElementRegistry
    function_registry: FunctionRegistry
    cell_lifecycle_registry: CellLifecycleRegistry
    virtual_file_registry: VirtualFileRegistry
    virtual_files_supported: bool
    stream: Stream
    stdout: Stdout | None
    stderr: Stderr | None
    children: list[RuntimeContext]
    parent: RuntimeContext | None

    @property
    @abc.abstractmethod
    def graph(self) -> dataflow.DirectedGraph:
        pass

    @property
    @abc.abstractmethod
    def globals(self) -> dict[str, Any]:
        pass

    @property
    @abc.abstractmethod
    def execution_context(self) -> ExecutionContext | None:
        pass

    @property
    @abc.abstractmethod
    def user_config(self) -> MarimoConfig:
        pass

    @property
    @abc.abstractmethod
    def cell_id(self) -> Optional[CellId_t]:
        """Get the cell id of the currently executing cell, if any."""
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
        pass

    @contextmanager
    @abc.abstractmethod
    def provide_ui_ids(self, prefix: str) -> Iterator[None]:
        pass

    @abc.abstractmethod
    def take_id(self) -> str:
        pass

    @abc.abstractmethod
    def register_state_update(self, state: State[Any]) -> None:
        pass

    @contextmanager
    @abc.abstractmethod
    def with_cell_id(self, cell_id: CellId_t) -> Iterator[None]:
        pass

    def add_child(self, runtime_context: RuntimeContext) -> None:
        if runtime_context not in self.children:
            self.children.append(runtime_context)

    def remove_child(self, runtime_context: RuntimeContext) -> None:
        self.children.remove(runtime_context)
        assert runtime_context not in self.children

    @contextmanager
    def install(self) -> Iterator[None]:
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
        pass


class _ThreadLocalContext(threading.local):
    """Thread-local container that holds thread/session-specific state."""

    def __init__(self) -> None:
        self.runtime_context: Optional[RuntimeContext] = None

    def initialize(self, runtime_context: RuntimeContext) -> None:
        self.runtime_context = runtime_context


class ContextNotInitializedError(Exception):
    pass


# Stores session-specific state, which is thread-local (relevant for run
# mode, in which every session runs in its own thread). Each thread
# must explicitly initialize this object.
_THREAD_LOCAL_CONTEXT = _ThreadLocalContext()


def initialize_context(runtime_context: RuntimeContext) -> None:
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


def runtime_context_installed() -> bool:
    try:
        get_context()
    except ContextNotInitializedError:
        return False
    else:
        return True
