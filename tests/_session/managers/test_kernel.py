# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import multiprocessing
import os
import signal
import subprocess
import sys
import time
from unittest.mock import Mock

import pytest

from marimo._ast.app_config import _AppConfig
from marimo._config.manager import get_default_config_manager
from marimo._runtime.commands import AppMetadata
from marimo._session.managers import KernelManagerImpl
from marimo._session.model import SessionMode
from marimo._utils.subprocess import try_kill_process_and_group


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
def test_try_kill_process_and_group_kills_grandchild() -> None:
    """SIGTERM must propagate to the full process group, not just the leader.

    Spawns `bash` in its own session (setsid) so it becomes a new process
    group leader, then forks a grandchild `sleep 60`. Verifies that
    `try_kill_process_and_group` on the bash parent also kills the
    grandchild — the property PR #9257 introduced.
    """
    p = subprocess.Popen(
        ["bash", "-c", "sleep 60 & echo $!; exec 1>/dev/null; wait"],
        start_new_session=True,
        stdout=subprocess.PIPE,
    )
    assert p.stdout is not None
    grandchild_pid = int(p.stdout.readline().strip())
    try:
        try_kill_process_and_group(p)
        p.wait(timeout=5)

        # The grandchild is reparented to init once bash exits; `kill(pid, 0)`
        # can briefly return success during the OS teardown window, so poll
        # with a generous ceiling we never actually approach in practice.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and _is_alive(grandchild_pid):
            time.sleep(0.001)
        assert not _is_alive(grandchild_pid), (
            f"grandchild {grandchild_pid} survived process-group kill"
        )
    finally:
        if p.poll() is None:
            p.kill()
            p.wait(timeout=5)
        if _is_alive(grandchild_pid):
            try:
                os.kill(grandchild_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_close_kernel_calls_try_kill_process_and_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KernelManagerImpl.close_kernel must route shutdown through
    try_kill_process_and_group so user-spawned subprocesses are reaped."""
    captured: list[object] = []
    monkeypatch.setattr(
        "marimo._session.managers.kernel.try_kill_process_and_group",
        captured.append,
    )

    queue_manager = Mock()
    queue_manager.win32_interrupt_queue = None

    manager = KernelManagerImpl(
        queue_manager=queue_manager,
        mode=SessionMode.EDIT,
        configs={},
        app_metadata=AppMetadata(
            query_params={},
            filename="test.py",
            cli_args={},
            argv=None,
            app_config=_AppConfig(),
        ),
        config_manager=get_default_config_manager(current_path=None),
        virtual_file_storage="shared_memory",
        redirect_console_to_browser=False,
    )

    fake_task = Mock(spec=multiprocessing.Process)
    fake_task.is_alive.return_value = False
    manager.kernel_task = fake_task

    manager.close_kernel()

    assert captured == [fake_task]
    queue_manager.close_queues.assert_called_once()
