# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
import signal
import subprocess
from collections.abc import Callable, Mapping, Sequence
from typing import (
    IO,
    Any,
    Literal,
    overload,
)

from marimo import _loggers
from marimo._session.queue import ProcessLike
from marimo._utils.platform import is_windows

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
    text: Literal[False] | None = ...,
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
            preexec_fn=preexec_fn,
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


_REAP_TASKS: set[asyncio.Task[None]] = set()


def _process_finished(process: ProcessLike) -> bool:
    """Return whether the process has finished without blocking."""
    # NB: It is not safe to call os.waitpid() directly because
    # apparently Popen.poll() and multiprcoessing.Process.is_alive()
    # assume that they are the ones that reap zombie processes.
    poll = getattr(process, "poll", None)
    if poll is not None:
        return poll() is not None
    return not process.is_alive()


async def cancel_pending_reaps() -> None:
    """Cancel and await any in-flight reap tasks.

    Call from a server shutdown hook so asyncio doesn't emit
    "Task was destroyed but it is pending" when the loop closes.
    """
    tasks = list(_REAP_TASKS)
    for t in tasks:
        t.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _reap_process_unix(process: ProcessLike, pgid: int | None) -> None:
    pid = process.pid
    await asyncio.sleep(5.0)
    if _process_finished(process):
        return

    LOGGER.warning(
        "Process %s did not respond to SIGTERM. Force killing.", pid
    )
    try:
        if pgid is not None:
            os.killpg(pgid, signal.SIGKILL)
        elif pid is not None:
            os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return

    wait_for_s = 10
    waited_s = 0
    while (
        not (process_finished := _process_finished(process))
        and waited_s < wait_for_s
    ):
        await asyncio.sleep(1.0)
        waited_s += 1

    if not process_finished:
        LOGGER.warning(
            "Waited for 10s, but process %s has still not quit ...", pid
        )
        return


def try_kill_process_and_group(process: ProcessLike) -> None:
    """Attempt to kill the process group to which process belongs.

    Refuses to kill the group if it the current process belongs to it.

    Regardless, tries to kill the process.

    If running in an event loop, starts a task to reap the process on Unix-like
    systems. If not running in an event loop, it is the caller's responsibility
    to reap the process.
    """
    pid = process.pid
    if pid is None:
        return

    if is_windows():
        # TODO(akshayka): Investigate whether we need to kill an entire
        # process group on Windows, and if so how ...
        process.terminate()
        return

    pgid = os.getpgid(pid)
    target_pgid: int | None
    if pgid == os.getpgrp():
        # This should never happen ... the kernel process makes sure to
        # call setsid and become the group leader
        LOGGER.warning("The target's pgid matches the server's (%d)", pgid)
        target_pgid = None
        process.terminate()
    else:
        target_pgid = pgid
        os.killpg(pgid, signal.SIGTERM)

    if _process_finished(process):
        return

    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_reap_process_unix(process, target_pgid))
        _REAP_TASKS.add(task)
        task.add_done_callback(_REAP_TASKS.discard)
    except RuntimeError:
        pass
