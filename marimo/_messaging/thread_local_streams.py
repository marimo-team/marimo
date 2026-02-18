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
from typing import TYPE_CHECKING

from marimo._messaging.types import Stderr, Stdout

if TYPE_CHECKING:
    from collections.abc import Iterable


_PROXIES_INSTALLED = False


class ThreadLocalStreamProxy(io.TextIOBase):
    """A proxy that dispatches writes to a per-thread stream.

    When a thread has registered a stream via set_thread_local_streams(),
    writes go there; otherwise they fall through to the original stream
    (real sys.stdout / sys.stderr).
    """

    def __init__(self, original: io.TextIOBase, name: str) -> None:
        self._original = original
        self._local = threading.local()
        self._name = name

    # -- per-thread registration -------------------------------------------

    def _set_stream(self, stream: io.TextIOBase) -> None:
        self._local.stream = stream

    def _clear_stream(self) -> None:
        self._local.stream = None

    def _get_stream(self) -> io.TextIOBase:
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
    global _PROXIES_INSTALLED
    if _PROXIES_INSTALLED:
        return
    sys.stdout = ThreadLocalStreamProxy(sys.stdout, "<stdout>")  # type: ignore[assignment]
    sys.stderr = ThreadLocalStreamProxy(sys.stderr, "<stderr>")  # type: ignore[assignment]
    _PROXIES_INSTALLED = True


def uninstall_thread_local_proxies() -> None:
    """Remove thread-local proxies, restoring the original streams."""
    global _PROXIES_INSTALLED
    if not _PROXIES_INSTALLED:
        return
    stdout = sys.stdout
    stderr = sys.stderr
    if isinstance(stdout, ThreadLocalStreamProxy):
        sys.stdout = stdout._original  # type: ignore[assignment]
    if isinstance(stderr, ThreadLocalStreamProxy):
        sys.stderr = stderr._original  # type: ignore[assignment]
    _PROXIES_INSTALLED = False


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
