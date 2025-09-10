"""Adapter classes for marimo-lsp to interface with marimo's core APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from marimo._server.types import ProcessLike

if TYPE_CHECKING:
    import subprocess


T = TypeVar("T")


class PopenProcessLike(ProcessLike):
    """Wraps `subprocess.Popen` as a `ProcessLike`.

    Provides the `ProcessLike` protocol required by marimo's KernelManager.
    """

    def __init__(self, inner: subprocess.Popen) -> None:
        """Initialize with a subprocess.Popen instance."""
        self.inner = inner

    @property
    def pid(self) -> int | None:
        """Get the process ID."""
        return self.inner.pid

    def is_alive(self) -> bool:
        """Check if the process is still running."""
        return self.inner.poll() is None

    def terminate(self) -> None:
        """Terminate the process."""
        self.inner.terminate()
