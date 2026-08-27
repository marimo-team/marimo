# Copyright 2026 Marimo. All rights reserved.
"""Single entry point for invoking the uv CLI.

All marimo code that shells out to uv and captures its output goes through
`uv()`. Failures surface as `UvCommandError` (or a refined subclass when the
failure mode is recognized), so callers recover on typed errors instead of
matching stderr text at each call site.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import TYPE_CHECKING

from marimo._environments.errors import EnvironmentManagerError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

UV_INSTALL_HINT = (
    "Install uv from https://docs.astral.sh/uv/getting-started/installation/"
)


class UvError(EnvironmentManagerError):
    """Base for all failures invoking uv."""


class UvNotFoundError(UvError):
    """uv is not installed or not on the PATH."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or f"uv must be installed. {UV_INSTALL_HINT}")


class UvCommandError(UvError):
    """A uv command exited with a nonzero status.

    Refined subclasses identify failure modes marimo recovers from; catching
    `UvCommandError` always remains a safe catch-all, so callers degrade
    gracefully if uv's output changes and a refinement stops matching.
    """

    def __init__(
        self,
        command: Sequence[str],
        returncode: int,
        stdout: str,
        stderr: str,
    ) -> None:
        self.command = list(command)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(
            f"`{' '.join(self.command)}` exited with code {returncode}:\n"
            + (stderr.strip() or stdout.strip())
        )


class UvMissingScriptMetadataError(UvCommandError):
    """The target script has no PEP 723 inline metadata block."""


class UvResolutionError(UvCommandError):
    """uv could not resolve the requested set of dependencies."""


class UvCacheWriteError(UvCommandError):
    """uv could not write to its distribution cache (e.g. read-only FS)."""


# Failure modes recognized in uv's stderr, most specific first. Each pattern
# is matched case-insensitively and annotated with the uv version it was
# validated against; tests exercise real uv so CI notices drift.
_REFINEMENTS: list[tuple[tuple[str, ...], type[UvCommandError]]] = [
    # uv 0.12.0
    (
        ("does not contain a pep 723 metadata tag",),
        UvMissingScriptMetadataError,
    ),
    # uv 0.12.0
    (("no solution found when resolving",), UvResolutionError),
    # uv ~0.9.7
    (
        (
            "failed to write to the distribution cache",
            "operation not permitted",
        ),
        UvCacheWriteError,
    ),
]


def _refine(completed: subprocess.CompletedProcess[str]) -> UvCommandError:
    stderr_lowered = completed.stderr.lower()
    error_type: type[UvCommandError] = UvCommandError
    for patterns, refined in _REFINEMENTS:
        if any(pattern in stderr_lowered for pattern in patterns):
            error_type = refined
            break
    return error_type(
        completed.args,
        completed.returncode,
        completed.stdout,
        completed.stderr,
    )


def find_uv_bin() -> str:
    return os.environ.get("UV", "uv")


def is_uv_available() -> bool:
    """Whether uv can be invoked.

    An explicit `UV` environment variable is trusted as-is (uv sets it when it
    spawns marimo, and it may point outside the PATH); otherwise the PATH is
    checked for a `uv` binary.
    """
    uv_bin = find_uv_bin()
    return uv_bin != "uv" or shutil.which("uv") is not None


def require_uv_bin() -> str:
    """Return the uv binary to invoke, raising `UvNotFoundError` if absent."""
    if not is_uv_available():
        raise UvNotFoundError()
    return find_uv_bin()


def uv(
    args: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a uv command and capture its output.

    Raises `UvNotFoundError` if uv is not installed and `UvCommandError` (or
    a refined subclass) on nonzero exit. `subprocess.TimeoutExpired`
    propagates when `timeout` elapses. When `env` is given it replaces the
    inherited environment. Not for interactive or streaming use: output is
    captured, and stdin is closed so uv can never hang waiting for input.
    """
    command = [find_uv_bin(), *args]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            stdin=subprocess.DEVNULL,
            env=dict(env) if env is not None else None,
            cwd=cwd,
            timeout=timeout,
            # A kernel interrupt must not propagate to uv; run it in its
            # own session (ignored on Windows).
            start_new_session=True,
        )
    except FileNotFoundError as e:
        raise UvNotFoundError() from e
    if completed.returncode != 0:
        raise _refine(completed)
    return completed
