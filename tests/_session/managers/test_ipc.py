# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from marimo._session.managers.ipc import construct_kernel_env


@pytest.mark.requires("zmq")
class TestIPCConnection:
    def test_input_channel_direction(self) -> None:
        """Test that input flows from host to kernel (not vice versa).

        Regression test for #7972 where the input channel Push/Pull
        directions were inverted, causing input() to fail in sandbox mode.
        """
        from marimo._ipc.connection import Connection

        host_conn, connection_info = Connection.create()
        kernel_conn = Connection.connect(connection_info)

        # Allow ZeroMQ connections to establish
        time.sleep(0.05)

        try:
            # Host sends input to kernel (what happens when user
            # responds to an input() prompt)
            test_input = "user response"
            host_conn.input.queue.put(test_input)

            # Kernel receives input
            received = kernel_conn.input.queue.get(timeout=1.0)
            assert received == test_input
        finally:
            host_conn.close()
            kernel_conn.close()


@pytest.mark.requires("zmq")
class TestIPCKernelManagerImpl:
    def test_venv_python_initial_value(self) -> None:
        """Test that venv_python is None before kernel starts."""
        from unittest.mock import MagicMock

        from marimo._session.managers.ipc import (
            IPCKernelManagerImpl,
            IPCQueueManagerImpl,
        )
        from marimo._session.model import SessionMode

        # Create minimal mocks for construction
        mock_ipc = MagicMock()
        queue_manager = IPCQueueManagerImpl(mock_ipc)
        connection_info = MagicMock()
        configs: dict = {}
        app_metadata = MagicMock()
        config_manager = MagicMock()

        # Create IPCKernelManagerImpl without starting kernel
        kernel_manager = IPCKernelManagerImpl(
            queue_manager=queue_manager,
            connection_info=connection_info,
            mode=SessionMode.EDIT,
            configs=configs,
            app_metadata=app_metadata,
            config_manager=config_manager,
        )

        # venv_python should be None before kernel starts
        assert kernel_manager.venv_python is None

    def test_venv_python_property_returns_stored_value(self) -> None:
        """Test that venv_python property returns the stored _venv_python value."""
        from unittest.mock import MagicMock

        from marimo._session.managers.ipc import (
            IPCKernelManagerImpl,
            IPCQueueManagerImpl,
        )
        from marimo._session.model import SessionMode

        # Create minimal mocks for construction
        mock_ipc = MagicMock()
        queue_manager = IPCQueueManagerImpl(mock_ipc)
        connection_info = MagicMock()
        configs: dict = {}
        app_metadata = MagicMock()
        config_manager = MagicMock()

        kernel_manager = IPCKernelManagerImpl(
            queue_manager=queue_manager,
            connection_info=connection_info,
            mode=SessionMode.EDIT,
            configs=configs,
            app_metadata=app_metadata,
            config_manager=config_manager,
        )

        # Manually set the internal state (simulating what start_kernel does)
        kernel_manager._venv_python = "/path/to/sandbox/venv/python"

        # venv_python property should return the stored value
        assert kernel_manager.venv_python == "/path/to/sandbox/venv/python"


class TestSubprocessWrapper:
    def test_exitcode_uses_popen_returncode(self) -> None:
        from marimo._session.managers.ipc import _SubprocessWrapper

        process = MagicMock()
        process.poll.return_value = -9
        wrapper = _SubprocessWrapper(process)

        assert wrapper.exitcode == -9


@pytest.mark.requires("zmq")
class TestIPCQueueManagerImpl:
    def test_from_ipc_factory(self) -> None:
        """Test that IPCQueueManagerImpl.from_ipc() creates a valid instance."""
        from marimo._ipc import QueueManager as IPCQueueManager
        from marimo._session.managers.ipc import IPCQueueManagerImpl

        # Create the underlying IPC queue manager
        ipc_queue_manager, connection_info = IPCQueueManager.create()

        # Create wrapper using factory method
        wrapper = IPCQueueManagerImpl.from_ipc(ipc_queue_manager)

        # Verify wrapper has access to queues
        assert wrapper.control_queue is not None
        assert wrapper.completion_queue is not None
        assert wrapper.input_queue is not None
        assert wrapper.stream_queue is not None
        assert wrapper.set_ui_element_queue is not None

        # connection_info should be valid
        assert connection_info is not None

        # Clean up
        wrapper.close_queues()

    def test_from_ipc_equals_direct_init(self) -> None:
        """Test that from_ipc() and __init__() produce equivalent results."""
        from marimo._ipc import QueueManager as IPCQueueManager
        from marimo._session.managers.ipc import IPCQueueManagerImpl

        ipc_queue_manager, _ = IPCQueueManager.create()

        # Create using factory
        via_factory = IPCQueueManagerImpl.from_ipc(ipc_queue_manager)
        # Create using __init__ directly
        via_init = IPCQueueManagerImpl(ipc_queue_manager)

        # Both should reference the same underlying IPC manager
        assert via_factory._ipc is via_init._ipc

        # Clean up
        via_factory.close_queues()


class TestConstructKernelEnv:
    """Tests for construct_kernel_env, the pure-function that builds the
    environment dict for a kernel subprocess.

    Three scenarios are covered matching the real call-sites in
    IPCKernelManagerImpl.start_kernel():
      1. Ephemeral sandbox  (is_ephemeral_sandbox=True, writable=True)
      2. Configured writable venv  (is_ephemeral_sandbox=False, writable=True)
      3. Configured read-only venv with PYTHONPATH injection
    """

    BASE_ENV: dict[str, str] = {"PATH": "/usr/bin"}
    SANDBOX_PYTHON = "/tmp/sandbox/.venv/bin/python"
    CONFIGURED_PYTHON = "/home/user/.venvs/nb/bin/python"

    # -- ephemeral sandbox -------------------------------------------------

    def test_ephemeral_sandbox(self) -> None:
        env = construct_kernel_env(
            base_env={**self.BASE_ENV, "UV_PROJECT_ENVIRONMENT": "/old"},
            venv_python=self.SANDBOX_PYTHON,
            is_ephemeral_sandbox=True,
            writable=True,
        )
        # VIRTUAL_ENV points to the venv root (two parents above python)
        assert (
            Path(env["VIRTUAL_ENV"]) == Path(self.SANDBOX_PYTHON).parent.parent
        )
        # UV_PROJECT_ENVIRONMENT must be removed so the kernel doesn't
        # inherit the outer uv project.
        assert "UV_PROJECT_ENVIRONMENT" not in env
        # Ephemeral sandboxes are always writable.
        assert env["MARIMO_MANAGE_SCRIPT_METADATA"] == "true"

    def test_inherited_sandbox_identity_is_stripped(self) -> None:
        """A configured-venv kernel inside a sandboxed server must not
        inherit script routing from the server's environment."""
        env = construct_kernel_env(
            base_env={
                **self.BASE_ENV,
                "MARIMO_SANDBOX_MODE": "multi",
                "MARIMO_MANAGE_SCRIPT_METADATA": "true",
            },
            venv_python=self.CONFIGURED_PYTHON,
            is_ephemeral_sandbox=False,
            writable=False,
        )
        assert "MARIMO_SANDBOX_MODE" not in env
        assert "MARIMO_MANAGE_SCRIPT_METADATA" not in env

    # -- configured venvs --------------------------------------------------

    def test_configured_readonly_venv_with_pythonpath(self) -> None:
        env = construct_kernel_env(
            base_env=self.BASE_ENV,
            venv_python=self.CONFIGURED_PYTHON,
            is_ephemeral_sandbox=False,
            writable=False,
            kernel_pythonpath="/usr/lib/python3.11/site-packages",
        )
        assert env["PYTHONPATH"] == "/usr/lib/python3.11/site-packages"
        # Should NOT touch sandbox-only vars.
        assert "VIRTUAL_ENV" not in env
        assert "MARIMO_MANAGE_SCRIPT_METADATA" not in env

    def test_pythonpath_merges_with_existing(self) -> None:
        env = construct_kernel_env(
            base_env={**self.BASE_ENV, "PYTHONPATH": "/existing"},
            venv_python=self.CONFIGURED_PYTHON,
            is_ephemeral_sandbox=False,
            writable=False,
            kernel_pythonpath="/new",
        )
        assert env["PYTHONPATH"] == f"/new{os.pathsep}/existing"

    def test_writable_sets_manage_script_metadata(self) -> None:
        env = construct_kernel_env(
            base_env=self.BASE_ENV,
            venv_python=self.CONFIGURED_PYTHON,
            is_ephemeral_sandbox=False,
            writable=True,
        )
        assert env["MARIMO_MANAGE_SCRIPT_METADATA"] == "true"

    # -- safety ------------------------------------------------------------

    def test_does_not_mutate_base_env(self) -> None:
        base = {**self.BASE_ENV, "UV_PROJECT_ENVIRONMENT": "/old"}
        construct_kernel_env(
            base_env=base,
            venv_python=self.SANDBOX_PYTHON,
            is_ephemeral_sandbox=True,
            writable=True,
        )
        assert "UV_PROJECT_ENVIRONMENT" in base
        assert "VIRTUAL_ENV" not in base


class TestVirtualFileStorage:
    @staticmethod
    def _kernel_args(**overrides: object) -> object:
        from marimo._ast.app_config import _AppConfig
        from marimo._config.config import DEFAULT_CONFIG
        from marimo._ipc.types import ConnectionInfo, KernelArgs
        from marimo._runtime.commands import AppMetadata

        kwargs: dict = {
            "configs": {},
            "app_metadata": AppMetadata(
                query_params={}, cli_args={}, app_config=_AppConfig()
            ),
            "user_config": DEFAULT_CONFIG,
            "log_level": 0,
            "profile_path": None,
            "connection_info": ConnectionInfo(
                control=1,
                ui_element=2,
                completion=3,
                win32_interrupt=None,
                input=4,
                stream=5,
            ),
        }
        kwargs.update(overrides)
        return KernelArgs(**kwargs)

    def test_kernel_args_roundtrip(self) -> None:
        from marimo._ipc.types import KernelArgs

        args = self._kernel_args(virtual_file_storage="shared_memory")
        decoded = KernelArgs.decode_json(args.encode_json())
        assert decoded.virtual_file_storage == "shared_memory"

    def test_payload_without_field_decodes_to_none(self) -> None:
        """A payload from an older launcher lacks the field entirely."""
        import json

        from marimo._ipc.types import KernelArgs

        payload = json.loads(self._kernel_args().encode_json())
        payload.pop("virtual_file_storage")
        decoded = KernelArgs.decode_json(json.dumps(payload).encode())
        assert decoded.virtual_file_storage is None

    def test_manager_requests_shared_memory_when_available(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from marimo._session.managers.ipc import _virtual_file_storage
        from marimo._utils import platform

        monkeypatch.setattr(
            platform, "check_shared_memory_available", lambda: (True, "")
        )
        assert _virtual_file_storage() == "shared_memory"

    def test_manager_falls_back_to_none_without_shm(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from marimo._session.managers.ipc import _virtual_file_storage
        from marimo._utils import platform

        monkeypatch.setattr(
            platform,
            "check_shared_memory_available",
            lambda: (False, "/dev/shm unavailable"),
        )
        assert _virtual_file_storage() is None


def _make_manager(filename: str | None = None) -> object:
    from unittest.mock import MagicMock

    from marimo._session.managers.ipc import (
        IPCKernelManagerImpl,
        IPCQueueManagerImpl,
    )
    from marimo._session.model import SessionMode

    app_metadata = MagicMock()
    app_metadata.filename = filename
    return IPCKernelManagerImpl(
        queue_manager=IPCQueueManagerImpl(MagicMock()),
        connection_info=MagicMock(),
        mode=SessionMode.EDIT,
        configs={},
        app_metadata=app_metadata,
        config_manager=MagicMock(),
    )


class TestProfilePath:
    def test_none_without_profile_dir(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from marimo._config.settings import GLOBAL_SETTINGS

        monkeypatch.setattr(GLOBAL_SETTINGS, "PROFILE_DIR", None)
        assert _make_manager("nb.py").profile_path is None

    def test_derived_from_profile_dir_and_filename(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from marimo._config.settings import GLOBAL_SETTINGS

        monkeypatch.setattr(GLOBAL_SETTINGS, "PROFILE_DIR", str(tmp_path))
        path = _make_manager("/some/dir/nb.py").profile_path
        assert path is not None
        assert path.startswith(str(tmp_path))
        assert "nb.py" in os.path.basename(path)


class TestCloseKernel:
    def _closable_manager(self) -> object:
        from unittest.mock import MagicMock

        manager = _make_manager("nb.py")
        manager.queue_manager = MagicMock()
        process = MagicMock()
        process.poll.return_value = None
        manager._process = process
        manager.kernel_task = None
        return manager

    def test_graceful_waits_bounded_for_exit(self) -> None:
        from marimo._runtime import commands
        from marimo._session.managers.ipc import GRACEFUL_EXIT_TIMEOUT

        manager = self._closable_manager()
        manager.close_kernel(graceful=True)

        (request,), _ = manager.queue_manager.put_control_request.call_args
        assert isinstance(request, commands.StopKernelCommand)
        manager.queue_manager.close_queues.assert_called_once()
        manager._process.wait.assert_called_once_with(
            timeout=GRACEFUL_EXIT_TIMEOUT
        )

    def test_default_close_does_not_wait(self) -> None:
        manager = self._closable_manager()
        manager.close_kernel()
        manager._process.wait.assert_not_called()

    def test_profiling_close_waits_for_flush(self) -> None:
        from marimo._session.managers.ipc import PROFILE_FLUSH_TIMEOUT

        manager = self._closable_manager()
        manager._profile_path = "/tmp/profile.stats"
        manager.close_kernel()
        manager._process.wait.assert_called_once_with(
            timeout=PROFILE_FLUSH_TIMEOUT
        )


class TestAwaitHandshakeLine:
    @staticmethod
    def _await(manager: object, handshake: object, deadline: float) -> str:
        from collections import deque

        return manager._await_handshake_line(
            handshake, deadline, deque(), ["python", "-m", "kernel"]
        )

    def test_returns_pending_line(self) -> None:
        import queue
        import subprocess
        import sys as _sys

        manager = _make_manager("nb.py")
        manager._process = subprocess.Popen(
            [_sys.executable, "-c", "import time; time.sleep(30)"]
        )
        try:
            handshake: queue.Queue[str] = queue.Queue()
            handshake.put("KERNEL_READY")
            line = self._await(
                manager, handshake, deadline=time.monotonic() + 5
            )
            assert line == "KERNEL_READY"
        finally:
            manager._process.kill()
            manager._process.wait()

    def test_child_exit_fails_fast_with_exit_code(self) -> None:
        import queue
        import subprocess
        import sys as _sys

        from marimo._session.managers.ipc import KernelStartupError

        manager = _make_manager("nb.py")
        manager._process = subprocess.Popen(
            [_sys.executable, "-c", "import sys; sys.exit(3)"]
        )
        manager._process.wait()
        with pytest.raises(KernelStartupError, match="exit code 3"):
            self._await(manager, queue.Queue(), deadline=time.monotonic() + 30)

    def test_line_printed_just_before_exit_is_not_lost(self) -> None:
        import queue
        import subprocess
        import sys as _sys

        manager = _make_manager("nb.py")
        manager._process = subprocess.Popen([_sys.executable, "-c", "pass"])
        manager._process.wait()
        handshake: queue.Queue[str] = queue.Queue()
        handshake.put("KERNEL_READY")
        line = self._await(manager, handshake, deadline=time.monotonic() + 5)
        assert line == "KERNEL_READY"

    def test_hung_child_times_out_and_is_killed(self) -> None:
        import queue
        import subprocess
        import sys as _sys

        from marimo._session.managers.ipc import KernelStartupError

        manager = _make_manager("nb.py")
        manager._process = subprocess.Popen(
            [_sys.executable, "-c", "import time; time.sleep(60)"]
        )
        try:
            with pytest.raises(
                KernelStartupError, match="did not become ready"
            ):
                self._await(
                    manager, queue.Queue(), deadline=time.monotonic() - 1
                )
            manager._process.wait(timeout=10)
            assert manager._process.poll() is not None
        finally:
            if manager._process.poll() is None:
                manager._process.kill()
                manager._process.wait()


class TestParseKernelInfo:
    def test_full_line(self) -> None:
        from marimo._session.managers.ipc import _parse_kernel_info

        pid, exe = _parse_kernel_info("KERNEL_INFO 1234 /env/bin/python")
        assert pid == 1234
        assert exe == "/env/bin/python"

    def test_tolerates_absence_and_junk(self) -> None:
        from marimo._session.managers.ipc import _parse_kernel_info

        assert _parse_kernel_info("") == (None, None)
        assert _parse_kernel_info("something else") == (None, None)
        assert _parse_kernel_info("KERNEL_INFO not-a-pid") == (None, None)

    def test_pid_only(self) -> None:
        from marimo._session.managers.ipc import _parse_kernel_info

        assert _parse_kernel_info("KERNEL_INFO 99") == (99, None)


def test_launch_kernel_handshake_reports_identity() -> None:
    """The kernel prints KERNEL_READY then KERNEL_INFO <pid> <exe>, so a
    manager separated from the kernel by a launcher can target it."""
    import subprocess
    import sys as _sys

    code = (
        "from unittest.mock import patch, MagicMock\n"
        "import marimo._ipc.launch_kernel as lk\n"
        "with patch.object(\n"
        "    lk.KernelArgs, 'decode_json', return_value=MagicMock()\n"
        "), patch.object(lk.QueueManager, 'connect', MagicMock()), \\\n"
        "        patch.object(lk.runtime, 'launch_kernel', MagicMock()):\n"
        "    lk.main()\n"
    )
    completed = subprocess.run(
        [_sys.executable, "-c", code],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    assert completed.returncode == 0, completed.stderr
    lines = completed.stdout.splitlines()
    assert lines[0] == "KERNEL_READY"
    from marimo._session.managers.ipc import _parse_kernel_info

    pid, exe = _parse_kernel_info(lines[1])
    assert pid is not None
    assert exe is not None
