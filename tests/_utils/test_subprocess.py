# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING, cast
from unittest.mock import Mock, patch

import pytest

from marimo._session.queue import ProcessLike
from marimo._utils.subprocess import (
    ProcessReaper,
    safe_popen,
    try_kill_process_and_group,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


class TestSafePopen:
    def test_successful_popen(self):
        proc = safe_popen(
            ["echo", "hello"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert proc is not None
        stdout, _ = proc.communicate()
        assert b"hello" in stdout
        proc.wait()

    def test_returns_none_on_file_not_found(self):
        result = safe_popen(["nonexistent_binary_abc123"])
        assert result is None

    def test_returns_none_on_permission_error(self):
        with patch(
            "subprocess.Popen", side_effect=PermissionError("not allowed")
        ):
            result = safe_popen(["echo", "hello"])
            assert result is None

    def test_returns_none_on_os_error(self):
        with patch(
            "subprocess.Popen",
            side_effect=OSError("some os error"),
        ):
            result = safe_popen(["echo", "hello"])
            assert result is None

    def test_returns_none_on_generic_exception(self):
        with patch(
            "subprocess.Popen",
            side_effect=RuntimeError("unexpected"),
        ):
            result = safe_popen(["echo", "hello"])
            assert result is None

    def test_passes_kwargs_through(self):
        proc = safe_popen(
            ["echo", "test"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )
        assert proc is not None
        stdout, _ = proc.communicate()
        assert "test" in stdout
        proc.wait()

    def test_returns_none_on_bad_cwd(self):
        result = safe_popen(
            ["echo", "hello"],
            cwd="/nonexistent/directory/abc123",
        )
        assert result is None


# Script mimics a marimo kernel / app host: calls setsid (like
# runtime.launch_kernel and app_host_main) to become its own process group
# leader, spawns two children — one in the same process group, one in a new
# session — prints their PIDs, then sleeps.
_PGROUP_LEADER_SCRIPT = """
import os, subprocess, sys, time
os.setsid()
child_pg = subprocess.Popen(
    [sys.executable, '-c', 'import time; time.sleep(15)']
)
child_newpg = subprocess.Popen(
    [sys.executable, '-c', 'import time; time.sleep(15)'],
    start_new_session=True,
)
print(child_pg.pid, child_newpg.pid, flush=True)
time.sleep(15)
"""


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _wait_until_dead(pid: int, timeout_s: float = 5.0) -> None:
    """Poll until the kernel has reaped `pid`, then assert.

    Tolerates the latency between SIGKILL delivery and the kernel actually
    tearing the process down — a bare `assert not _is_alive(pid)` immediately
    after a kill is racy.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline and _is_alive(pid):
        time.sleep(0.05)
    assert not _is_alive(pid)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
def test_try_kill_process_and_group_kills_pgroup_spares_new_session() -> None:
    """Covers the shutdown path used by KernelManagerImpl, IPCKernelManagerImpl,
    and AppHost — all three delegate to try_kill_process_and_group.
    """
    leader = subprocess.Popen(
        [sys.executable, "-c", _PGROUP_LEADER_SCRIPT],
        stdout=subprocess.PIPE,
        text=True,
    )
    child_pg_pid = child_newpg_pid = 0
    try:
        assert leader.stdout is not None
        child_pg_pid, child_newpg_pid = (
            int(x) for x in leader.stdout.readline().split()
        )

        try_kill_process_and_group(cast(ProcessLike, leader))

        # wait() reaps the child so it doesn't linger as a zombie.
        assert leader.wait(timeout=5) is not None

        _wait_until_dead(child_pg_pid)
        assert _is_alive(child_newpg_pid)
    finally:
        for pid in (leader.pid, child_pg_pid, child_newpg_pid):
            if pid:
                try:
                    os.kill(pid, 9)
                except ProcessLookupError:
                    pass
        leader.wait(timeout=5)


_IGNORE_SIGTERM_SCRIPT = (
    "import signal, time\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "while True: time.sleep(1)\n"
)


@contextlib.contextmanager
def _spawn_group_leader(script: str) -> Iterator[subprocess.Popen[bytes]]:
    proc = subprocess.Popen(  # noqa: ASYNC220
        [sys.executable, "-c", script], start_new_session=True
    )
    pgid = os.getpgid(proc.pid)
    try:
        yield proc
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pgid, signal.SIGKILL)
        proc.wait(timeout=5)


def _kill_and_get_reaper(proc: subprocess.Popen[bytes]) -> ProcessReaper:
    reaper = try_kill_process_and_group(cast(ProcessLike, proc))
    assert reaper is not None
    return reaper


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
async def test_reaper_sigkills_child_that_ignores_sigterm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("marimo._utils.subprocess._SIGTERM_GRACE_S", 0.1)

    with _spawn_group_leader(_IGNORE_SIGTERM_SCRIPT) as proc:
        # Let the child install its handler before we signal it.
        await asyncio.sleep(0.5)
        await _kill_and_get_reaper(proc).wait()
        assert proc.returncode == -signal.SIGKILL


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
async def test_reaper_returns_once_child_exits_on_sigterm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("marimo._utils.subprocess._SIGTERM_GRACE_S", 60.0)

    with _spawn_group_leader("import time; time.sleep(60)") as proc:
        start = time.monotonic()
        await _kill_and_get_reaper(proc).wait()
        assert time.monotonic() - start < 10
        assert proc.returncode == -signal.SIGTERM


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
async def test_reaper_wait_defers_cancellation_until_reaped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("marimo._utils.subprocess._SIGTERM_GRACE_S", 0.1)

    with _spawn_group_leader(_IGNORE_SIGTERM_SCRIPT) as proc:
        await asyncio.sleep(0.5)
        waiter = asyncio.create_task(_kill_and_get_reaper(proc).wait())
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert proc.returncode == -signal.SIGKILL


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
async def test_reaper_wait_logs_reap_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_reap(_process: ProcessLike, _pgid: int | None) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(
        "marimo._utils.subprocess._reap_process_unix", failing_reap
    )

    with (
        _spawn_group_leader(_IGNORE_SIGTERM_SCRIPT) as proc,
        patch("marimo._utils.subprocess.LOGGER") as logger,
    ):
        await asyncio.sleep(0.5)
        await _kill_and_get_reaper(proc).wait()
        logger.warning.assert_called_once()


@pytest.mark.parametrize("windows", [False, True])
def test_exited_process_is_not_signalled(windows: bool) -> None:
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait(timeout=10)
    with (
        patch("marimo._utils.subprocess.is_windows", return_value=windows),
        patch("marimo._utils.subprocess.subprocess.run") as taskkill,
        patch("marimo._utils.subprocess.os.getpgid", create=True) as getpgid,
    ):
        try_kill_process_and_group(cast(ProcessLike, process))
    taskkill.assert_not_called()
    getpgid.assert_not_called()


def test_windows_process_cleanup_falls_back_when_taskkill_times_out() -> None:
    process = Mock(pid=123)
    process.poll.return_value = None
    with (
        patch("marimo._utils.subprocess.is_windows", return_value=True),
        patch(
            "marimo._utils.subprocess.subprocess.run",
            side_effect=subprocess.TimeoutExpired("taskkill", 5),
        ) as taskkill,
    ):
        try_kill_process_and_group(cast(ProcessLike, process))
    taskkill.assert_called_once_with(
        ["taskkill", "/T", "/F", "/PID", "123"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
    )
    process.terminate.assert_called_once_with()
