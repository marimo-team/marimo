# Copyright 2024 Marimo. All rights reserved.
"""Thread-local context for the runtime

Each client gets its own context.
"""


from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator, Optional

from marimo._plugins.ui._core.ids import IDProvider, NoIDProviderException
from marimo._runtime.cell_lifecycle_registry import CellLifecycleRegistry
from marimo._runtime.functions import FunctionRegistry

if TYPE_CHECKING:
    from marimo._ast.cell import CellId_t
    from marimo._messaging.types import Stream
    from marimo._plugins.ui._core.registry import UIElementRegistry
    from marimo._runtime.runtime import Kernel
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
class RuntimeContext:
    """Encapsulates runtime state for a session."""

    kernel: Kernel
    ui_element_registry: UIElementRegistry
    function_registry: FunctionRegistry
    cell_lifecycle_registry: CellLifecycleRegistry
    virtual_file_registry: VirtualFileRegistry
    virtual_files_supported: bool
    stream: Stream
    _id_provider: Optional[IDProvider] = None

    @property
    def cell_id(self) -> Optional[CellId_t]:
        """Get the cell id of the currently executing cell, if any."""
        if self.kernel.execution_context is not None:
            return self.kernel.execution_context.cell_id
        return None

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


def initialize_context(
    kernel: Kernel, stream: Stream, virtual_files_supported: bool = True
) -> None:
    """Initializes thread-local/session-specific context.

    Must be called exactly once for each client thread.
    """
    from marimo._plugins.ui._core.registry import UIElementRegistry
    from marimo._runtime.virtual_file import VirtualFileRegistry

    try:
        get_context()
        raise RuntimeError("RuntimeContext was already initialized.")
    except ContextNotInitializedError:
        global _THREAD_LOCAL_CONTEXT
        runtime_context = RuntimeContext(
            kernel=kernel,
            ui_element_registry=UIElementRegistry(),
            function_registry=FunctionRegistry(),
            cell_lifecycle_registry=CellLifecycleRegistry(),
            virtual_file_registry=VirtualFileRegistry(),
            virtual_files_supported=virtual_files_supported,
            stream=stream,
        )
        _THREAD_LOCAL_CONTEXT.initialize(runtime_context=runtime_context)


def teardown_context() -> None:
    """Unset the context, for testing."""
    global _THREAD_LOCAL_CONTEXT
    _THREAD_LOCAL_CONTEXT.runtime_context = None


def get_context() -> RuntimeContext:
    """Return the runtime context.

    Throws a ContextNotInitializedError if the context has not been
    created (which happens when running as a script).
    """
    if _THREAD_LOCAL_CONTEXT.runtime_context is None:
        raise ContextNotInitializedError
    return _THREAD_LOCAL_CONTEXT.runtime_context
