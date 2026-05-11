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
