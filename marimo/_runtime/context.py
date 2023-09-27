# Copyright 2023 Marimo. All rights reserved.
"""Thread-local context for the runtime

Each client gets its own context.
"""


from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator, Optional

from marimo._plugins.ui._core.ids import IDProvider, NoIDProviderException

if TYPE_CHECKING:
    from marimo._messaging.streams import Stderr, Stdout, Stream
    from marimo._plugins.stateless.mpl._mpl import InteractiveMplRegistry
    from marimo._plugins.ui._core.registry import UIElementRegistry
    from marimo._runtime.runtime import Kernel


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


class RuntimeContext(threading.local):
    """Encapsulates runtime state for a session; thread-local."""

    def __init__(self) -> None:
        self._kernel: Optional[Kernel] = None
        self._ui_element_registry: Optional[UIElementRegistry] = None
        self._stream: Optional[Stream] = None
        self._stdout: Optional[Stdout] = None
        self._stderr: Optional[Stderr] = None
        self._id_provider: Optional[IDProvider] = None
        self._initialized: bool = False

    def initialize(
        self,
        kernel: Kernel,
        ui_element_registry: UIElementRegistry,
        interactive_mpl_registry: InteractiveMplRegistry,
        stream: Stream,
        stdout: Optional[Stdout],
        stderr: Optional[Stderr],
    ) -> None:
        self._kernel = kernel
        self._ui_element_registry = ui_element_registry
        self._interactive_mpl_registry = interactive_mpl_registry
        self._stream = stream
        self._stdout = stdout
        self._stderr = stderr
        self._initialized = True

    @property
    def kernel(self) -> Kernel:
        assert self._kernel is not None
        return self._kernel

    @property
    def ui_element_registry(self) -> UIElementRegistry:
        assert self._ui_element_registry is not None
        return self._ui_element_registry

    @property
    def interactive_mpl_registry(self) -> InteractiveMplRegistry:
        assert self._interactive_mpl_registry
        return self._interactive_mpl_registry

    @property
    def stream(self) -> Stream:
        assert self._stream is not None
        return self._stream

    @property
    def stdout(self) -> Optional[Stdout]:
        return self._stdout

    @property
    def stderr(self) -> Optional[Stderr]:
        return self._stderr

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
    def initialized(self) -> bool:
        return self._initialized


_RUNTIME_CONTEXT = RuntimeContext()


def initialize_context(
    kernel: Kernel,
    ui_element_registry: UIElementRegistry,
    interactive_mpl_registry: InteractiveMplRegistry,
    stream: Stream,
    stdout: Optional[Stdout],
    stderr: Optional[Stderr],
) -> None:
    """Must be called exactly once for each client thread."""
    if _RUNTIME_CONTEXT._initialized:
        raise RuntimeError("RuntimeContext was already initialized.")
    _RUNTIME_CONTEXT.initialize(
        kernel=kernel,
        ui_element_registry=ui_element_registry,
        interactive_mpl_registry=interactive_mpl_registry,
        stream=stream,
        stdout=stdout,
        stderr=stderr,
    )


def get_context() -> RuntimeContext:
    return _RUNTIME_CONTEXT
