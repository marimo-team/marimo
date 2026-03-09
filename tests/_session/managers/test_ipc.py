# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
import subprocess
import sys
import time
from unittest.mock import patch

import pytest

from marimo._session.managers.ipc import (
    _forward_pipe,
    _forward_subprocess_output,
)

# Small helper script that mimics the IPC kernel handshake then writes
# to both stdout and stderr, exactly like a real kernel would.
_KERNEL_SCRIPT = (
    "import sys; "
    "sys.stdout.write('KERNEL_READY\\n'); sys.stdout.flush(); "
    "sys.stdout.write('hello out\\n'); sys.stdout.flush(); "
    "sys.stderr.write('hello err\\n'); sys.stderr.flush()"
)


class TestForwardSubprocessOutput:
    def test_forwarding_delivers_output(self) -> None:
        """With _forward_subprocess_output, pipe data reaches the parent."""
        proc = subprocess.Popen(
            [sys.executable, "-c", _KERNEL_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert proc.stdout is not None
        # Consume only the KERNEL_READY handshake, same as start_kernel.
        ready = proc.stdout.readline()
        assert ready.strip() == b"KERNEL_READY"

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch("sys.stdout", stdout_buf), patch("sys.stderr", stderr_buf):
            threads = _forward_subprocess_output(proc)
            for t in threads:
                t.join(timeout=5)

        proc.wait()
        assert "hello out" in stdout_buf.getvalue()
        assert "hello err" in stderr_buf.getvalue()

    def test_forward_pipe_drains_on_closed_dest(self) -> None:
        """When dest is closed, the pipe is still drained (no SIGPIPE)."""
        proc = subprocess.Popen(
            [sys.executable, "-c", "print('line')"],
            stdout=subprocess.PIPE,
        )
        assert proc.stdout is not None
        dest = io.StringIO()
        dest.close()

        # Should not raise — the pipe is fully drained even though
        # nothing can be written.
        _forward_pipe(proc.stdout, dest)
        proc.wait()


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
