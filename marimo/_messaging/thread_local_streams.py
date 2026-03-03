# Copyright 2026 Marimo. All rights reserved.
"""Thread-local stream proxy for run mode.

In run mode, multiple sessions share the same process. Each session runs in its
own thread and needs sys.stdout / sys.stderr to route output to that session's
frontend connection.

ThreadLocalStreamProxy wraps the real sys.stdout / sys.stderr once at process
level and dispatches writes to a per-thread stream registered via
set_thread_local_streams().
"""

from __future__ import annotations

import io
import sys
import threading
from typing import TYPE_CHECKING, TextIO, Union

from marimo._messaging.types import Stderr, Stdout

if TYPE_CHECKING:
    from collections.abc import Iterable


_proxies_installed = False
_install_lock = threading.Lock()
_original_stdout: TextIO | None = None
_original_stderr: TextIO | None = None


class ThreadLocalStreamProxy(io.TextIOBase):
    """A proxy that dispatches writes to a per-thread stream.

    When a thread has registered a stream via set_thread_local_streams(),
    writes go there; otherwise they fall through to the original stream
    (real sys.stdout / sys.stderr).
    """

    def __init__(
        self, original: Union[io.TextIOBase, TextIO], name: str
    ) -> None:
        self._original = original
        self._local = threading.local()
        self._name = name
        # Expose the underlying binary buffer so that code writing to
        # sys.stdout.buffer (e.g. package installation logging) keeps working.
        self.buffer: io.BufferedIOBase | None = getattr(
            original, "buffer", None
        )

    # -- per-thread registration -------------------------------------------

    def _set_stream(self, stream: io.TextIOBase) -> None:
        self._local.stream = stream

    def _clear_stream(self) -> None:
        self._local.stream = None

    def _get_stream(self) -> Union[io.TextIOBase, TextIO]:
        stream = getattr(self._local, "stream", None)
        return stream if stream is not None else self._original

    # -- TextIOBase interface ----------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def encoding(self) -> str:  # type: ignore[override]
        return getattr(self._get_stream(), "encoding", "utf-8")

    @property
    def errors(self) -> str | None:  # type: ignore[override]
        return getattr(self._get_stream(), "errors", None)

    def write(self, data: str) -> int:
        return self._get_stream().write(data)

    def writelines(self, lines: Iterable[str]) -> None:  # type: ignore[override]
        self._get_stream().writelines(lines)

    def flush(self) -> None:
        self._get_stream().flush()

    def fileno(self) -> int:
        return self._original.fileno()

    def isatty(self) -> bool:
        return self._original.isatty()

    def readable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False


def install_thread_local_proxies() -> None:
    """Install thread-local proxies as sys.stdout / sys.stderr (idempotent).

    Called once from the main server thread before kernel threads are spawned.
    """
    global _proxies_installed, _original_stdout, _original_stderr
    with _install_lock:
        if _proxies_installed:
            return
        _original_stdout = sys.stdout
        _original_stderr = sys.stderr
        sys.stdout = ThreadLocalStreamProxy(sys.stdout, "<stdout>")  # type: ignore[assignment]
        sys.stderr = ThreadLocalStreamProxy(sys.stderr, "<stderr>")  # type: ignore[assignment]
        _proxies_installed = True


def uninstall_thread_local_proxies() -> None:
    """Remove thread-local proxies, restoring the original streams."""
    global _proxies_installed, _original_stdout, _original_stderr
    with _install_lock:
        if not _proxies_installed:
            return
        if _original_stdout is not None:
            sys.stdout = _original_stdout  # type: ignore[assignment]
        if _original_stderr is not None:
            sys.stderr = _original_stderr  # type: ignore[assignment]
        _original_stdout = None
        _original_stderr = None
        _proxies_installed = False


def set_thread_local_streams(
    stdout: Stdout | None, stderr: Stderr | None
) -> None:
    """Register per-thread streams (call from each session thread)."""
    if isinstance(sys.stdout, ThreadLocalStreamProxy) and stdout is not None:
        sys.stdout._set_stream(stdout)  # type: ignore[union-attr]
    if isinstance(sys.stderr, ThreadLocalStreamProxy) and stderr is not None:
        sys.stderr._set_stream(stderr)  # type: ignore[union-attr]


def clear_thread_local_streams() -> None:
    """Clear per-thread streams (call when a session thread exits)."""
    if isinstance(sys.stdout, ThreadLocalStreamProxy):
        sys.stdout._clear_stream()  # type: ignore[union-attr]
    if isinstance(sys.stderr, ThreadLocalStreamProxy):
        sys.stderr._clear_stream()  # type: ignore[union-attr]
