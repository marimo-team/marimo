# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from typing import (
    IO,
    Any,
    Literal,
    Optional,
    overload,
)

from marimo import _loggers

LOGGER = _loggers.marimo_logger()

# Type aliases matching typeshed's subprocess stubs
_CMD = str | bytes | Sequence[str | bytes]
_ENV = Mapping[str, str] | Mapping[bytes, bytes]
_FILE = int | IO[Any] | None


@overload
def safe_popen(
    args: _CMD,
    bufsize: int = ...,
    executable: str | bytes | None = ...,
    stdin: _FILE = ...,
    stdout: _FILE = ...,
    stderr: _FILE = ...,
    preexec_fn: Callable[[], Any] | None = ...,
    close_fds: bool = ...,
    shell: bool = ...,
    cwd: str | bytes | None = ...,
    env: _ENV | None = ...,
    universal_newlines: bool = ...,
    startupinfo: Any = ...,
    creationflags: int = ...,
    restore_signals: bool = ...,
    start_new_session: bool = ...,
    pass_fds: Sequence[int] = ...,
    *,
    encoding: str,
    errors: str | None = ...,
    text: bool | None = ...,
    user: str | int | None = ...,
    group: str | int | None = ...,
    extra_groups: Sequence[str | int] | None = ...,
    umask: int = ...,
    pipesize: int = ...,
) -> subprocess.Popen[str] | None: ...


@overload
def safe_popen(
    args: _CMD,
    bufsize: int = ...,
    executable: str | bytes | None = ...,
    stdin: _FILE = ...,
    stdout: _FILE = ...,
    stderr: _FILE = ...,
    preexec_fn: Callable[[], Any] | None = ...,
    close_fds: bool = ...,
    shell: bool = ...,
    cwd: str | bytes | None = ...,
    env: _ENV | None = ...,
    universal_newlines: bool = ...,
    startupinfo: Any = ...,
    creationflags: int = ...,
    restore_signals: bool = ...,
    start_new_session: bool = ...,
    pass_fds: Sequence[int] = ...,
    *,
    encoding: str | None = ...,
    errors: str,
    text: bool | None = ...,
    user: str | int | None = ...,
    group: str | int | None = ...,
    extra_groups: Sequence[str | int] | None = ...,
    umask: int = ...,
    pipesize: int = ...,
) -> subprocess.Popen[str] | None: ...


@overload
def safe_popen(
    args: _CMD,
    bufsize: int = ...,
    executable: str | bytes | None = ...,
    stdin: _FILE = ...,
    stdout: _FILE = ...,
    stderr: _FILE = ...,
    preexec_fn: Callable[[], Any] | None = ...,
    close_fds: bool = ...,
    shell: bool = ...,
    cwd: str | bytes | None = ...,
    env: _ENV | None = ...,
    *,
    universal_newlines: Literal[True],
    startupinfo: Any = ...,
    creationflags: int = ...,
    restore_signals: bool = ...,
    start_new_session: bool = ...,
    pass_fds: Sequence[int] = ...,
    encoding: str | None = ...,
    errors: str | None = ...,
    text: bool | None = ...,
    user: str | int | None = ...,
    group: str | int | None = ...,
    extra_groups: Sequence[str | int] | None = ...,
    umask: int = ...,
    pipesize: int = ...,
) -> subprocess.Popen[str] | None: ...


@overload
def safe_popen(
    args: _CMD,
    bufsize: int = ...,
    executable: str | bytes | None = ...,
    stdin: _FILE = ...,
    stdout: _FILE = ...,
    stderr: _FILE = ...,
    preexec_fn: Callable[[], Any] | None = ...,
    close_fds: bool = ...,
    shell: bool = ...,
    cwd: str | bytes | None = ...,
    env: _ENV | None = ...,
    universal_newlines: bool = ...,
    startupinfo: Any = ...,
    creationflags: int = ...,
    restore_signals: bool = ...,
    start_new_session: bool = ...,
    pass_fds: Sequence[int] = ...,
    *,
    text: Literal[True],
    encoding: str | None = ...,
    errors: str | None = ...,
    user: str | int | None = ...,
    group: str | int | None = ...,
    extra_groups: Sequence[str | int] | None = ...,
    umask: int = ...,
    pipesize: int = ...,
) -> subprocess.Popen[str] | None: ...


@overload
def safe_popen(
    args: _CMD,
    bufsize: int = ...,
    executable: str | bytes | None = ...,
    stdin: _FILE = ...,
    stdout: _FILE = ...,
    stderr: _FILE = ...,
    preexec_fn: Callable[[], Any] | None = ...,
    close_fds: bool = ...,
    shell: bool = ...,
    cwd: str | bytes | None = ...,
    env: _ENV | None = ...,
    universal_newlines: Literal[False] = ...,
    startupinfo: Any = ...,
    creationflags: int = ...,
    restore_signals: bool = ...,
    start_new_session: bool = ...,
    pass_fds: Sequence[int] = ...,
    *,
    text: Optional[Literal[False]] = ...,
    encoding: None = ...,
    errors: None = ...,
    user: str | int | None = ...,
    group: str | int | None = ...,
    extra_groups: Sequence[str | int] | None = ...,
    umask: int = ...,
    pipesize: int = ...,
) -> subprocess.Popen[bytes] | None: ...


@overload
def safe_popen(
    args: _CMD,
    bufsize: int = ...,
    executable: str | bytes | None = ...,
    stdin: _FILE = ...,
    stdout: _FILE = ...,
    stderr: _FILE = ...,
    preexec_fn: Callable[[], Any] | None = ...,
    close_fds: bool = ...,
    shell: bool = ...,
    cwd: str | bytes | None = ...,
    env: _ENV | None = ...,
    universal_newlines: bool = ...,
    startupinfo: Any = ...,
    creationflags: int = ...,
    restore_signals: bool = ...,
    start_new_session: bool = ...,
    pass_fds: Sequence[int] = ...,
    *,
    text: bool | None = ...,
    encoding: str | None = ...,
    errors: str | None = ...,
    user: str | int | None = ...,
    group: str | int | None = ...,
    extra_groups: Sequence[str | int] | None = ...,
    umask: int = ...,
    pipesize: int = ...,
) -> subprocess.Popen[Any] | None: ...


def safe_popen(
    args: _CMD,
    bufsize: int = -1,
    executable: str | bytes | None = None,
    stdin: _FILE = None,
    stdout: _FILE = None,
    stderr: _FILE = None,
    preexec_fn: Callable[[], Any] | None = None,
    close_fds: bool = True,
    shell: bool = False,
    cwd: str | bytes | None = None,
    env: _ENV | None = None,
    universal_newlines: bool = False,
    startupinfo: Any = None,
    creationflags: int = 0,
    restore_signals: bool = True,
    start_new_session: bool = False,
    pass_fds: Sequence[int] = (),
    *,
    text: bool | None = None,
    encoding: str | None = None,
    errors: str | None = None,
    user: str | int | None = None,
    group: str | int | None = None,
    extra_groups: Sequence[str | int] | None = None,
    umask: int = -1,
    pipesize: int = -1,
    # Note: process_group is omitted because it was added in Python 3.11
) -> subprocess.Popen[Any] | None:
    """Wrapper around subprocess.Popen that never raises.

    Returns None and logs the error if the subprocess cannot be created
    (e.g. FileNotFoundError, PermissionError, OSError).
    """
    try:
        return subprocess.Popen(
            args,
            bufsize=bufsize,
            executable=executable,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            preexec_fn=preexec_fn,  # noqa: PLW1509
            close_fds=close_fds,
            shell=shell,
            cwd=cwd,
            env=env,
            universal_newlines=universal_newlines,
            startupinfo=startupinfo,
            creationflags=creationflags,
            restore_signals=restore_signals,
            start_new_session=start_new_session,
            pass_fds=pass_fds,
            text=text,
            encoding=encoding,
            errors=errors,
            user=user,
            group=group,
            extra_groups=extra_groups,
            umask=umask,
            pipesize=pipesize,
        )
    except Exception as e:
        LOGGER.error("Failed to create subprocess for command %s: %s", args, e)
        return None
