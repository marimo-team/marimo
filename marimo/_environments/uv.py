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
import sys
import threading
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._environments.errors import EnvironmentManagerError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

LOGGER = _loggers.marimo_logger()

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


def uv_stream(
    args: Sequence[str],
    on_output: Callable[[str], None],
    *,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Runs a uv command, streaming its diagnostics to a callback.

    uv writes progress to stderr and machine-readable output to stdout:
    stderr lines stream to `on_output` (and this process's stderr) while
    stdout is captured for the caller. `on_output` runs in the calling
    thread, so callbacks that rely on thread-local state, such as a
    kernel's notification context, keep working. Failures raise the same
    refined errors as `uv()`.
    """
    command = [find_uv_bin(), *args]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            env=dict(env) if env is not None else None,
            cwd=cwd,
            bufsize=0,
            # A kernel interrupt must not propagate to uv; run it in its
            # own session (ignored on Windows).
            start_new_session=True,
        )
    except FileNotFoundError as e:
        raise UvNotFoundError() from e

    assert process.stdout is not None
    assert process.stderr is not None
    stdout_pipe = process.stdout
    stdout_chunks: list[bytes] = []

    def drain_stdout() -> None:
        stdout_chunks.append(stdout_pipe.read())
        stdout_pipe.close()

    reader = threading.Thread(target=drain_stdout, daemon=True)
    reader.start()

    stderr_lines: list[bytes] = []
    for line in iter(process.stderr.readline, b""):
        stderr_lines.append(line)
        decoded = line.decode("utf-8", errors="replace")
        # The terminal tee is best effort: a kernel replaces sys.stderr
        # with a redirect whose `buffer` may be None, and nothing here
        # may stop the stream or deadlock uv.
        try:
            buffer = getattr(sys.stderr, "buffer", None)
            if buffer is not None:
                buffer.write(line)
                buffer.flush()
            else:
                sys.stderr.write(decoded)
        except Exception:
            pass
        try:
            on_output(decoded)
        except Exception:
            LOGGER.exception("Failed to stream uv output")
    process.stderr.close()
    returncode = process.wait()
    reader.join()

    completed = subprocess.CompletedProcess(
        command,
        returncode,
        stdout=b"".join(stdout_chunks).decode("utf-8", errors="replace"),
        stderr=b"".join(stderr_lines).decode("utf-8", errors="replace"),
    )
    if completed.returncode != 0:
        raise _refine(completed)
    return completed


def script_command_env() -> dict[str, str]:
    """Environment for uv script commands.

    A script's environment is selected by the script and its metadata; an
    enclosing project or virtualenv must not redirect it or warn about
    the mismatch.
    """
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    env.pop("UV_PROJECT_ENVIRONMENT", None)
    return env
