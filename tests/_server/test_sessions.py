# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import functools
import inspect
import os
import queue
import sys
import time
from multiprocessing.queues import Queue as MPQueue
from typing import Any
from unittest.mock import MagicMock

from marimo._ast.app import App, InternalApp
from marimo._config.manager import get_default_config_manager
from marimo._runtime.requests import (
    AppMetadata,
    CreationRequest,
    ExecutionRequest,
    SetUIElementValueRequest,
)
from marimo._server.file_manager import AppFileManager
from marimo._server.model import ConnectionState, SessionMode
from marimo._server.sessions import KernelManager, QueueManager, Session
from marimo._server.utils import initialize_asyncio

initialize_asyncio()


app_metadata = AppMetadata(
    query_params={"some_param": "some_value"}, filename="test.py", cli_args={}
)


# TODO(akshayka): automatically do this for every test in our test suite
def save_and_restore_main(f):
    """Kernels swap out the main module; restore it after running tests"""

    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        main = sys.modules["__main__"]
        try:
            f(*args, **kwargs)
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
def test_kernel_manager_run_mode() -> None:
    # Mock objects and data for testing
    queue_manager = QueueManager(use_multiprocessing=False)
    mode = SessionMode.RUN

    # Instantiate a KernelManager
    kernel_manager = KernelManager(
        queue_manager,
        mode,
        {},
        app_metadata,
        get_default_config_manager(current_path=None),
        virtual_files_supported=True,
    )

    kernel_manager.start_kernel()

    # Assert startup
    assert kernel_manager.kernel_task is not None
    assert kernel_manager._read_conn is None
    assert kernel_manager.is_alive()

    kernel_manager.close_kernel()

    # Assert shutdown
    kernel_manager.kernel_task.join()
    assert not kernel_manager.is_alive()
    assert queue_manager.input_queue.empty()
    assert queue_manager.control_queue.empty()


@save_and_restore_main
def test_kernel_manager_edit_mode() -> None:
    # Mock objects and data for testing
    queue_manager = QueueManager(use_multiprocessing=True)
    mode = SessionMode.EDIT

    # Instantiate a KernelManager
    kernel_manager = KernelManager(
        queue_manager,
        mode,
        {},
        app_metadata,
        get_default_config_manager(current_path=None),
        virtual_files_supported=True,
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
    # these are known to be mp.Queue
    queue_manager.input_queue.join_thread()  # type: ignore
    queue_manager.control_queue.join_thread()  # type: ignore


@save_and_restore_main
def test_kernel_manager_interrupt(tmp_path) -> None:
    queue_manager = QueueManager(use_multiprocessing=True)
    mode = SessionMode.EDIT

    kernel_manager = KernelManager(
        queue_manager,
        mode,
        {},
        app_metadata,
        get_default_config_manager(current_path=None),
        virtual_files_supported=True,
    )

    # Assert startup
    kernel_manager.start_kernel()
    assert kernel_manager.kernel_task is not None
    assert kernel_manager._read_conn is not None
    assert kernel_manager.is_alive()
    if sys.platform == "win32":
        import random
        import string

        # Having trouble persisting the write to a temp file on Windows
        file = (
            "".join(random.choice(string.ascii_uppercase) for _ in range(10))
            + ".txt"
        )
    else:
        file = str(tmp_path / "output.txt")

    with open(file, "w") as f:
        f.write("-1")

    queue_manager.control_queue.put(
        CreationRequest(
            execution_requests=tuple(
                [
                    ExecutionRequest(
                        cell_id="1",
                        code=inspect.cleandoc(
                            f"""
                            import time
                            with open("{file}", 'w') as f:
                                f.write('0')
                            time.sleep(5)
                            with open("{file}", 'w') as f:
                                f.write('1')
                            """
                        ),
                    )
                ]
            ),
            set_ui_element_value_request=SetUIElementValueRequest(
                object_ids=[], values=[]
            ),
        )
    )

    # give time for the file to be written to 0, but not enough for it to be
    # written to 1
    time.sleep(0.5)
    kernel_manager.interrupt_kernel()

    try:
        with open(file, "r") as f:
            assert f.read() == "0"
        # if kernel failed to interrupt, f will read as "1"
        time.sleep(1.5)
        with open(file, "r") as f:
            assert f.read() == "0"
    finally:
        if sys.platform == "win32":
            os.remove(file)

        assert queue_manager.input_queue.empty()
        assert queue_manager.control_queue.empty()

        # Assert shutdown
        kernel_manager.close_kernel()
        kernel_manager.kernel_task.join()
        assert not kernel_manager.is_alive()


@save_and_restore_main
def test_session() -> None:
    session_consumer: Any = MagicMock()
    session_consumer.connection_state.return_value = ConnectionState.OPEN
    queue_manager = QueueManager(use_multiprocessing=False)
    kernel_manager = KernelManager(
        queue_manager,
        SessionMode.RUN,
        {},
        app_metadata,
        get_default_config_manager(current_path=None),
        virtual_files_supported=True,
    )

    # Instantiate a Session
    session = Session(
        "test",
        session_consumer,
        queue_manager,
        kernel_manager,
        AppFileManager.from_app(InternalApp(App())),
    )

    # Assert startup
    assert session.room.main_consumer == session_consumer
    assert session._queue_manager == queue_manager
    assert session.kernel_manager == kernel_manager
    session_consumer.on_start.assert_called_once()
    assert session_consumer.on_stop.call_count == 0
    assert session.connection_state() == ConnectionState.OPEN

    session.close()

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
        queue_manager,
        SessionMode.RUN,
        {},
        AppMetadata(query_params={}, cli_args={}),
        get_default_config_manager(current_path=None),
        virtual_files_supported=True,
    )

    # Instantiate a Session
    session = Session(
        "test",
        session_consumer,
        queue_manager,
        kernel_manager,
        AppFileManager.from_app(InternalApp(App())),
    )

    # Assert startup
    assert session.room.main_consumer == session_consumer
    session_consumer.on_start.assert_called_once()
    assert session_consumer.on_stop.call_count == 0

    session.disconnect_consumer(session_consumer)

    # Assert shutdown of consumer
    assert session.room.main_consumer is None
    session_consumer.on_start.assert_called_once()
    session_consumer.on_stop.assert_called_once()
    assert session.connection_state() == ConnectionState.ORPHANED

    # Reconnect
    new_session_consumer = MagicMock()
    session.connect_consumer(new_session_consumer, main=True)
    assert session.room.main_consumer == new_session_consumer
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


@save_and_restore_main
def test_session_with_kiosk_consumers() -> None:
    session_consumer: Any = MagicMock()
    session_consumer.connection_state.return_value = ConnectionState.OPEN
    queue_manager = QueueManager(use_multiprocessing=False)
    kernel_manager = KernelManager(
        queue_manager,
        SessionMode.RUN,
        {},
        app_metadata,
        get_default_config_manager(current_path=None),
        virtual_files_supported=True,
    )

    # Instantiate a Session
    session = Session(
        "test",
        session_consumer,
        queue_manager,
        kernel_manager,
        AppFileManager.from_app(InternalApp(App())),
    )

    # Assert startup
    assert session.room.main_consumer == session_consumer
    assert session._queue_manager == queue_manager
    assert session.kernel_manager == kernel_manager
    session_consumer.on_start.assert_called_once()
    assert session_consumer.on_stop.call_count == 0
    assert session.connection_state() == ConnectionState.OPEN

    # Create a kiosk consumer
    kiosk_consumer: Any = MagicMock()
    kiosk_consumer.connection_state.return_value = ConnectionState.OPEN
    session.connect_consumer(kiosk_consumer, main=False)

    # Assert startup of kiosk consumer
    assert session.room.main_consumer != kiosk_consumer
    assert kiosk_consumer in session.room.consumers
    kiosk_consumer.on_start.assert_called_once()
    assert kiosk_consumer.on_stop.call_count == 0
    assert session.connection_state() == ConnectionState.OPEN

    session.close()
    session_consumer.connection_state.return_value = ConnectionState.CLOSED
    kiosk_consumer.connection_state.return_value = ConnectionState.CLOSED

    # Assert shutdown
    assert kernel_manager.kernel_task is not None
    kernel_manager.kernel_task.join()
    assert not kernel_manager.is_alive()
    assert queue_manager.input_queue.empty()
    assert queue_manager.control_queue.empty()
    session_consumer.on_start.assert_called_once()
    session_consumer.on_stop.assert_called_once()
    kiosk_consumer.on_start.assert_called_once()
    kiosk_consumer.on_stop.assert_called_once()
    assert session.connection_state() == ConnectionState.CLOSED
    assert not session.room.consumers
    assert session.room.main_consumer is None
