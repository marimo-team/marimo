# Copyright 2024 Marimo. All rights reserved.
import queue
from multiprocessing.queues import Queue as MPQueue
from typing import Any
from unittest.mock import MagicMock

from marimo._runtime.requests import AppMetadata
from marimo._server.model import SessionMode
from marimo._server.sessions import KernelManager, QueueManager, Session
from marimo._server.utils import initialize_asyncio

initialize_asyncio()


app_metadata = AppMetadata(filename="test.py")


def test_queue_manager() -> None:
    # Test with multiprocessing queues
    queue_manager_mp = QueueManager(use_multiprocessing=True)
    assert isinstance(queue_manager_mp.control_queue, MPQueue)
    assert isinstance(queue_manager_mp.input_queue, MPQueue)

    # Test with threading queues
    queue_manager_thread = QueueManager(use_multiprocessing=False)
    assert isinstance(queue_manager_thread.control_queue, queue.Queue)
    assert isinstance(queue_manager_thread.input_queue, queue.Queue)


def test_kernel_manager() -> None:
    # Mock objects and data for testing
    queue_manager = QueueManager(use_multiprocessing=False)
    mode = SessionMode.RUN

    # Instantiate a KernelManager
    kernel_manager = KernelManager(queue_manager, mode, {}, app_metadata)

    kernel_manager.start_kernel()

    # Assert startup
    assert kernel_manager.kernel_task is not None
    assert kernel_manager._read_conn is not None
    assert kernel_manager.is_alive()

    kernel_manager.close_kernel()

    # Assert shutdown
    kernel_manager.kernel_task.join()
    assert not kernel_manager.is_alive()
    assert queue_manager.input_queue.empty()
    assert queue_manager.control_queue.empty()


def test_session() -> None:
    session_handler: Any = MagicMock()
    queue_manager = QueueManager(use_multiprocessing=False)
    kernel_manager = KernelManager(
        queue_manager, SessionMode.RUN, {}, app_metadata
    )

    # Instantiate a Session
    session = Session(session_handler, queue_manager, kernel_manager)

    # Assert startup
    assert session.session_handler == session_handler
    assert session._queue_manager == queue_manager
    assert session.kernel_manager == kernel_manager
    session_handler.on_start.assert_called_once()
    assert session_handler.on_stop.call_count == 0

    session.close()

    # Assert shutdown
    assert kernel_manager.kernel_task is not None
    kernel_manager.kernel_task.join()
    assert not kernel_manager.is_alive()
    assert queue_manager.input_queue.empty()
    assert queue_manager.control_queue.empty()
    session_handler.on_start.assert_called_once()
    session_handler.on_stop.assert_called_once()
