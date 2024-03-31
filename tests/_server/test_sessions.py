# Copyright 2024 Marimo. All rights reserved.
import queue
import sys
from multiprocessing.queues import Queue as MPQueue
from typing import Any
from unittest.mock import MagicMock

from marimo._ast.app import App, InternalApp
from marimo._runtime.requests import AppMetadata
from marimo._server.file_manager import AppFileManager
from marimo._server.model import ConnectionState, SessionMode
from marimo._server.sessions import KernelManager, QueueManager, Session
from marimo._server.utils import initialize_asyncio

initialize_asyncio()


app_metadata = AppMetadata(
    query_params={"some_param": "some_value"},
    filename="test.py",
)


# TODO(akshayka): automatically do this for every test in our test suite
def save_and_restore_main(f):
    """Kernels swap out the main module; restore it after running tests"""

    def wrapper():
        main = sys.modules["__main__"]
        try:
            f()
        finally:
            sys.modules["__main__"] = main

    return wrapper


@save_and_restore_main
def test_queue_manager() -> None:
    # Test with multiprocessing queues
    queue_manager_mp = QueueManager(use_multiprocessing=True)
    assert isinstance(queue_manager_mp.control_queue, MPQueue)
    assert isinstance(queue_manager_mp.completion_queue, MPQueue)
    assert isinstance(queue_manager_mp.input_queue, MPQueue)

    # Test with threading queues
    queue_manager_thread = QueueManager(use_multiprocessing=False)
    assert isinstance(queue_manager_thread.control_queue, queue.Queue)
    assert isinstance(queue_manager_thread.completion_queue, queue.Queue)
    assert isinstance(queue_manager_thread.input_queue, queue.Queue)


@save_and_restore_main
def test_kernel_manager() -> None:
    # Mock objects and data for testing
    queue_manager = QueueManager(use_multiprocessing=False)
    mode = SessionMode.RUN

    # Instantiate a KernelManager
    kernel_manager = KernelManager(
        queue_manager, mode, {}, app_metadata, "pip"
    )

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


@save_and_restore_main
def test_session() -> None:
    session_consumer: Any = MagicMock()
    session_consumer.connection_state.return_value = ConnectionState.OPEN
    queue_manager = QueueManager(use_multiprocessing=False)
    kernel_manager = KernelManager(
        queue_manager, SessionMode.RUN, {}, app_metadata, "pip"
    )

    # Instantiate a Session
    session = Session(
        session_consumer,
        queue_manager,
        kernel_manager,
        AppFileManager.from_app(InternalApp(App())),
    )

    # Assert startup
    assert session.session_consumer == session_consumer
    assert session._queue_manager == queue_manager
    assert session.kernel_manager == kernel_manager
    session_consumer.on_start.assert_called_once()
    assert session_consumer.on_stop.call_count == 0
    assert session.connection_state() == ConnectionState.OPEN

    session.close()
    session_consumer.connection_state.return_value = ConnectionState.CLOSED

    # Assert shutdown
    assert kernel_manager.kernel_task is not None
    kernel_manager.kernel_task.join()
    assert not kernel_manager.is_alive()
    assert queue_manager.input_queue.empty()
    assert queue_manager.control_queue.empty()
    session_consumer.on_start.assert_called_once()
    session_consumer.on_stop.assert_called_once()
    assert session.connection_state() == ConnectionState.CLOSED


@save_and_restore_main
def test_session_disconnect_reconnect() -> None:
    session_consumer: Any = MagicMock()
    session_consumer.connection_state.return_value = ConnectionState.OPEN
    queue_manager = QueueManager(use_multiprocessing=False)
    kernel_manager = KernelManager(
        queue_manager, SessionMode.RUN, {}, AppMetadata(query_params={}), "pip"
    )

    # Instantiate a Session
    session = Session(
        session_consumer,
        queue_manager,
        kernel_manager,
        AppFileManager.from_app(InternalApp(App())),
    )

    # Assert startup
    assert session.session_consumer == session_consumer
    session_consumer.on_start.assert_called_once()
    assert session_consumer.on_stop.call_count == 0

    session.disconnect_consumer()

    # Assert shutdown of consumer
    assert session.session_consumer is None
    session_consumer.on_start.assert_called_once()
    session_consumer.on_stop.assert_called_once()
    assert session.connection_state() == ConnectionState.ORPHANED

    # Reconnect
    new_session_consumer = MagicMock()
    session.connect_consumer(new_session_consumer)
    assert session.session_consumer == new_session_consumer
    new_session_consumer.on_start.assert_called_once()
    assert new_session_consumer.on_stop.call_count == 0

    session.close()
    new_session_consumer.connection_state.return_value = ConnectionState.CLOSED

    # Assert shutdown
    assert kernel_manager.kernel_task is not None
    kernel_manager.kernel_task.join()
    assert not kernel_manager.is_alive()
    new_session_consumer.on_start.assert_called_once()
    new_session_consumer.on_stop.assert_called_once()
    assert session.connection_state() == ConnectionState.CLOSED
