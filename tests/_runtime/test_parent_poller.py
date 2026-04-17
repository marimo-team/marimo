# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import select
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from tests._utils.process_helpers import wait_until


def _wait_for_pipe_eof(read_fd: int, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        readable, _, _ = select.select([read_fd], [], [], max(remaining, 0.0))
        if not readable:
            continue

        data = os.read(read_fd, 4096)
        if data == b"":
            return

    pytest.fail(
        "Heartbeat pipe stayed open after the parent exited, which means "
        "a kernel descendant survived ParentPollerUnix shutdown."
    )


def _read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    return int(path.read_text())


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="ParentPollerUnix relies on Unix process semantics",
)
def test_parent_poller_uses_runtime_cleanup_before_killing_descendants(
    tmp_path: Path,
) -> None:
    ready_path = tmp_path / "ready"
    cleanup_path = tmp_path / "cleanup"
    kernel_pid_path = tmp_path / "kernel_pid"
    child_pid_path = tmp_path / "child_pid"
    read_fd, write_fd = os.pipe()

    heartbeat_code = textwrap.dedent(
        """
        import os
        import sys
        import time
        from pathlib import Path

        write_fd = int(sys.argv[1])
        child_pid_path = Path(sys.argv[2])

        child_pid_path.write_text(str(os.getpid()))
        try:
            while True:
                os.write(write_fd, b".")
                time.sleep(0.05)
        except BrokenPipeError:
            pass
        """
    )

    kernel_code = textwrap.dedent(
        """
        import copy
        import os
        import queue
        import subprocess
        import sys
        import threading
        import time
        from pathlib import Path

        import marimo._runtime.parent_poller as parent_poller
        import marimo._runtime.runtime as runtime_module
        from marimo._ast.app_config import _AppConfig
        from marimo._config.config import DEFAULT_CONFIG
        from marimo._runtime.commands import AppMetadata

        parent_pid = int(sys.argv[1])
        ready_path = Path(sys.argv[2])
        cleanup_path = Path(sys.argv[3])
        kernel_pid_path = Path(sys.argv[4])
        child_pid_path = Path(sys.argv[5])
        write_fd = int(sys.argv[6])
        heartbeat_code = sys.argv[7]

        parent_poller._PARENT_POLL_INTERVAL_SECONDS = 0.02
        parent_poller._PARENT_SHUTDOWN_WAIT_SECONDS = 0.5

        original_teardown = runtime_module.Kernel.teardown

        def patched_teardown(self):
            cleanup_path.write_text("teardown")
            return original_teardown(self)

        runtime_module.Kernel.teardown = patched_teardown

        kernel_pid_path.write_text(str(os.getpid()))

        def spawn_child_after_setsid() -> None:
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                if os.getpgrp() == os.getpid():
                    subprocess.Popen(
                        [
                            sys.executable,
                            "-c",
                            heartbeat_code,
                            str(write_fd),
                            str(child_pid_path),
                        ],
                        pass_fds=(write_fd,),
                    )
                    ready_path.write_text("ready")
                    return
                time.sleep(0.01)
            ready_path.write_text("setsid-timeout")

        threading.Thread(target=spawn_child_after_setsid, daemon=True).start()

        control_queue = queue.Queue()
        set_ui_element_queue = queue.Queue()
        completion_queue = queue.Queue()
        input_queue = queue.Queue(maxsize=1)
        stream_queue = queue.Queue()

        runtime_module.launch_kernel(
            control_queue=control_queue,
            set_ui_element_queue=set_ui_element_queue,
            completion_queue=completion_queue,
            input_queue=input_queue,
            stream_queue=stream_queue,
            socket_addr=None,
            is_edit_mode=False,
            configs={},
            app_metadata=AppMetadata(
                query_params={},
                cli_args={},
                app_config=_AppConfig(),
                argv=None,
                filename="test.py",
            ),
            user_config=copy.deepcopy(DEFAULT_CONFIG),
            virtual_file_storage=None,
            redirect_console_to_browser=False,
            interrupt_queue=None,
            profile_path=None,
            log_level=None,
            is_ipc=True,
            parent_pid=parent_pid,
        )
        """
    )

    launcher_code = textwrap.dedent(
        """
        import os
        import subprocess
        import sys
        import time
        from pathlib import Path

        ready_path = Path(sys.argv[1])
        cleanup_path = Path(sys.argv[2])
        kernel_pid_path = Path(sys.argv[3])
        child_pid_path = Path(sys.argv[4])
        write_fd = int(sys.argv[5])
        kernel_code = sys.argv[6]
        heartbeat_code = sys.argv[7]

        subprocess.Popen(
            [
                sys.executable,
                "-c",
                kernel_code,
                str(os.getpid()),
                str(ready_path),
                str(cleanup_path),
                str(kernel_pid_path),
                str(child_pid_path),
                str(write_fd),
                heartbeat_code,
            ],
            pass_fds=(write_fd,),
        )

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if ready_path.exists() and child_pid_path.exists():
                break
            time.sleep(0.02)

        os._exit(0)
        """
    )

    launcher = subprocess.Popen(
        [
            sys.executable,
            "-c",
            launcher_code,
            str(ready_path),
            str(cleanup_path),
            str(kernel_pid_path),
            str(child_pid_path),
            str(write_fd),
            kernel_code,
            heartbeat_code,
        ],
        cwd=str(Path(__file__).resolve().parents[2]),
        pass_fds=(write_fd,),
    )
    os.close(write_fd)

    try:
        launcher.wait(timeout=3)
        wait_until(
            lambda: (
                ready_path.exists()
                and ready_path.read_text() == "ready"
                and kernel_pid_path.exists()
                and child_pid_path.exists()
            ),
            timeout_seconds=3,
            message="Kernel subprocess tree did not become ready in time",
            poll_interval_seconds=0.02,
        )

        # Drain any startup bytes so the next read can observe EOF directly.
        pipe_closed = False
        while True:
            readable, _, _ = select.select([read_fd], [], [], 0)
            if not readable:
                break
            if os.read(read_fd, 4096) == b"":
                pipe_closed = True
                break

        wait_until(
            cleanup_path.exists,
            timeout_seconds=2,
            message=(
                "Kernel teardown did not run before parent-death shutdown "
                "forced the process group to exit."
            ),
            poll_interval_seconds=0.02,
        )
        if not pipe_closed:
            _wait_for_pipe_eof(read_fd, timeout_seconds=2)
    finally:
        kernel_pid = _read_pid(kernel_pid_path)
        child_pid = _read_pid(child_pid_path)

        if launcher.poll() is None:
            launcher.kill()
            launcher.wait(timeout=2)

        if kernel_pid is not None:
            try:
                os.killpg(kernel_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        os.close(read_fd)
