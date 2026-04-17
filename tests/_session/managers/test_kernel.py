# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import functools
import inspect
import json
import sys
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

import pytest

from marimo._ast.app_config import _AppConfig
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._config.manager import get_default_config_manager
from marimo._runtime.commands import (
    AppMetadata,
    CreateNotebookCommand,
    ExecuteCellCommand,
    UpdateUIElementCommand,
)
from marimo._session.managers import KernelManagerImpl, QueueManagerImpl
from marimo._session.model import SessionMode

if TYPE_CHECKING:
    from pathlib import Path

    import psutil

F = TypeVar("F", bound=Callable[..., Any])

app_metadata = AppMetadata(
    query_params={"some_param": "some_value"},
    filename="test.py",
    cli_args={},
    argv=None,
    app_config=_AppConfig(),
)


def save_and_restore_main(f: F) -> F:
    """Kernels swap out the main module; restore it after running tests."""

    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        main = sys.modules["__main__"]
        try:
            res = f(*args, **kwargs)
            if asyncio.iscoroutine(res):
                asyncio.run(res)
        finally:
            sys.modules["__main__"] = main

    return wrapper  # type: ignore[return-value]


def _wait_until(
    predicate: Callable[[], bool], timeout_seconds: float, message: str
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    pytest.fail(message)


def _cleanup_process(process: psutil.Process) -> None:
    import psutil

    try:
        process.terminate()
        try:
            process.wait(timeout=2)
        except psutil.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    except psutil.NoSuchProcess:
        pass


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="process-group shutdown semantics are Unix-only",
)
@save_and_restore_main
def test_close_kernel_returns_quickly_and_preserves_profile_dump(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    monkeypatch.setattr(GLOBAL_SETTINGS, "PROFILE_DIR", str(tmp_path))

    queue_manager = QueueManagerImpl(use_multiprocessing=True)
    kernel_manager = KernelManagerImpl(
        queue_manager=queue_manager,
        mode=SessionMode.EDIT,
        configs={},
        app_metadata=app_metadata,
        config_manager=get_default_config_manager(current_path=None),
        virtual_file_storage="shared_memory",
        redirect_console_to_browser=False,
    )

    kernel_manager.start_kernel()
    try:
        profile_path = kernel_manager.profile_path
        assert profile_path is not None

        start = time.monotonic()
        kernel_manager.close_kernel()
        elapsed = time.monotonic() - start

        assert elapsed < 1.0

        kernel_manager.wait_for_close(timeout=10)
        _wait_until(
            lambda: not kernel_manager.is_alive(),
            timeout_seconds=2,
            message="Kernel process did not exit after close_kernel()",
        )
        assert Path(profile_path).exists()
    finally:
        if kernel_manager.is_alive():
            kernel_manager.close_kernel()
        kernel_manager.wait_for_close(timeout=10)
        queue_manager.input_queue.join_thread()  # type: ignore[union-attr]
        queue_manager.control_queue.join_thread()  # type: ignore[union-attr]


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="process-group shutdown semantics are Unix-only",
)
@save_and_restore_main
def test_close_kernel_shuts_down_same_group_subprocesses_only(
    tmp_path: Path,
) -> None:
    import psutil

    queue_manager = QueueManagerImpl(use_multiprocessing=True)
    kernel_manager = KernelManagerImpl(
        queue_manager=queue_manager,
        mode=SessionMode.EDIT,
        configs={},
        app_metadata=app_metadata,
        config_manager=get_default_config_manager(current_path=None),
        virtual_file_storage="shared_memory",
        redirect_console_to_browser=False,
    )

    pid_file = tmp_path / "subprocess_pids.json"
    kernel_process: psutil.Process | None = None
    child_pg_process: psutil.Process | None = None
    child_newpg_process: psutil.Process | None = None

    kernel_manager.start_kernel()
    try:
        assert kernel_manager.kernel_task is not None
        assert kernel_manager.pid is not None

        queue_manager.put_control_request(
            CreateNotebookCommand(
                execution_requests=(
                    ExecuteCellCommand(
                        cell_id="1",
                        code=inspect.cleandoc(
                            f"""
                            import json
                            import os
                            import subprocess
                            import sys
                            import time
                            from pathlib import Path

                            output_path = Path({str(pid_file)!r})
                            cmd = [sys.executable, "-c", "import time; time.sleep(30)"]
                            child_pg = subprocess.Popen(
                                cmd, start_new_session=False
                            )
                            child_newpg = subprocess.Popen(
                                cmd, start_new_session=True
                            )
                            time.sleep(0.5)
                            output_path.write_text(
                                json.dumps(
                                    {{
                                        "kernel": os.getpid(),
                                        "child_pg": child_pg.pid,
                                        "child_newpg": child_newpg.pid,
                                    }}
                                )
                            )
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

        _wait_until(
            pid_file.exists,
            timeout_seconds=5,
            message="Kernel did not write subprocess PID file in time",
        )

        pids = json.loads(pid_file.read_text())
        kernel_process = psutil.Process(pids["kernel"])
        child_pg_process = psutil.Process(pids["child_pg"])
        child_newpg_process = psutil.Process(pids["child_newpg"])

        _wait_until(
            lambda: child_pg_process.is_running()
            and child_newpg_process.is_running(),
            timeout_seconds=2,
            message="Spawned subprocesses did not stay alive long enough",
        )

        kernel_manager.close_kernel()
        kernel_manager.wait_for_close(timeout=10)

        _wait_until(
            lambda: not kernel_manager.is_alive(),
            timeout_seconds=2,
            message="Kernel process did not exit after close_kernel()",
        )
        _wait_until(
            lambda: not child_pg_process.is_running(),
            timeout_seconds=2,
            message="Same-process-group child survived close_kernel()",
        )

        assert not kernel_process.is_running()
        assert child_newpg_process.is_running()
    finally:
        if kernel_manager.is_alive():
            kernel_manager.close_kernel()
        kernel_manager.wait_for_close(timeout=10)

        if child_newpg_process is not None:
            _cleanup_process(child_newpg_process)

        queue_manager.input_queue.join_thread()  # type: ignore[union-attr]
        queue_manager.control_queue.join_thread()  # type: ignore[union-attr]
