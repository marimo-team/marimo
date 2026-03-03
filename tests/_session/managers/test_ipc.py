# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import time

import pytest


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
