# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import os
import sys
import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from marimo._ast.app_config import _AppConfig
from marimo._config.manager import get_default_config_manager
from marimo._runtime.commands import (
    AppMetadata,
    CreateNotebookCommand,
    ExecuteCellCommand,
    UpdateUIElementCommand,
)
from marimo._session.managers import KernelManagerImpl, QueueManagerImpl
from marimo._session.model import SessionMode


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
def test_close_kernel_kills_user_spawned_subprocess(tmp_path: Path) -> None:
    """A subprocess spawned by kernel-executed user code must be killed when
    the kernel is closed."""
    pid_file = tmp_path / "child.pid"

    queue_manager = QueueManagerImpl(use_multiprocessing=True)
    kernel_manager = KernelManagerImpl(
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

    kernel_manager.start_kernel()
    try:
        assert kernel_manager.is_alive()

        queue_manager.control_queue.put(
            CreateNotebookCommand(
                execution_requests=(
                    ExecuteCellCommand(
                        cell_id="1",
                        code=inspect.cleandoc(
                            f"""
                            import subprocess
                            _proc = subprocess.Popen(["sleep", "60"])
                            with open("{pid_file}", "w") as _f:
                                _f.write(str(_proc.pid))
                            """
                        ),
                    ),
                ),
                cell_ids=("1",),
                set_ui_element_value_request=UpdateUIElementCommand(
                    object_ids=[], values=[]
                ),
                auto_run=True,
            )
        )

        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not pid_file.exists():
            time.sleep(0.05)
        assert pid_file.exists(), "kernel never spawned the subprocess"
        child_pid = int(pid_file.read_text())
        assert _is_alive(child_pid)
    finally:
        kernel_manager.close_kernel()

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and _is_alive(child_pid):
        time.sleep(0.05)
    try:
        assert not _is_alive(child_pid)
    finally:
        if _is_alive(child_pid):
            try:
                os.kill(child_pid, 9)
            except ProcessLookupError:
                pass
