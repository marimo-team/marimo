# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import cast
from unittest.mock import patch

import pytest

from marimo._session.queue import ProcessLike
from marimo._utils.subprocess import safe_popen, try_kill_process_and_group


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

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and _is_alive(child_pg_pid):
            time.sleep(0.05)

        assert not _is_alive(child_pg_pid)
        assert _is_alive(child_newpg_pid)
    finally:
        for pid in (leader.pid, child_pg_pid, child_newpg_pid):
            if pid:
                try:
                    os.kill(pid, 9)
                except ProcessLookupError:
                    pass
        leader.wait(timeout=5)
