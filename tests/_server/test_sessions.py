# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import functools
import inspect
import os
import queue
import sys
import threading
import time
from multiprocessing.queues import Queue as MPQueue
from pathlib import Path
from tempfile import NamedTemporaryFile
from textwrap import dedent
from typing import Any, Callable, TypeVar
from unittest.mock import MagicMock

import pytest

from marimo._ast.app import App, InternalApp
from marimo._ast.app_config import _AppConfig
from marimo._config.manager import (
    get_default_config_manager,
)
from marimo._messaging.notification import (
    NotificationMessage,
    UpdateCellCodesNotification,
)
from marimo._messaging.serde import deserialize_kernel_message
from marimo._messaging.types import KernelMessage
from marimo._runtime.requests import (
    AppMetadata,
    CreationRequest,
    ExecutionRequest,
    SetUIElementValueRequest,
    SyncGraphRequest,
)
from marimo._server.consumer import SessionConsumer
from marimo._server.file_router import AppFileRouter
from marimo._server.model import ConnectionState, SessionMode
from marimo._server.notebook import AppFileManager
from marimo._server.session.session_view import SessionView
from marimo._server.sessions import Session
from marimo._server.sessions.events import SessionEventBus
from marimo._server.sessions.managers import (
    KernelManagerImpl,
    QueueManagerImpl,
)
from marimo._server.sessions.session import (
    SessionImpl,
)
from marimo._server.sessions.session_manager import SessionManager
from marimo._server.utils import initialize_asyncio
from marimo._types.ids import ConsumerId, SessionId
from marimo._utils.marimo_path import MarimoPath

initialize_asyncio()

F = TypeVar("F", bound=Callable[..., Any])

app_metadata = AppMetadata(
    query_params={"some_param": "some_value"},
    filename="test.py",
    cli_args={},
    argv=None,
    app_config=_AppConfig(),
)


class MockSessionConsumer(SessionConsumer):
    def __init__(self) -> None:
        self.notify_calls: list[NotificationMessage] = []

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        pass

    def on_detach(self) -> None:
        pass

    @property
    def consumer_id(self) -> ConsumerId:
        return ConsumerId("test_consumer_id")

    def connection_state(self) -> ConnectionState:
        return ConnectionState.OPEN

    def notify(self, notification: KernelMessage) -> None:
        self.notify_calls.append(deserialize_kernel_message(notification))


# TODO(akshayka): automatically do this for every test in our test suite
def save_and_restore_main(f: F) -> F:
    """Kernels swap out the main module; restore it after running tests"""

    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        main = sys.modules["__main__"]
        try:
            res = f(*args, **kwargs)
            if asyncio.iscoroutine(res):
                asyncio.run(res)
            else:
                pass
        finally:
            sys.modules["__main__"] = main

    return wrapper  # type: ignore


session_id = SessionId("test")


@save_and_restore_main
def test_queue_manager() -> None:
    # Test with multiprocessing queues
    queue_manager_mp = QueueManagerImpl(use_multiprocessing=True)
    assert isinstance(queue_manager_mp.control_queue, MPQueue)
    assert isinstance(queue_manager_mp.completion_queue, MPQueue)
    assert isinstance(queue_manager_mp.input_queue, MPQueue)

    # Test with threading queues
    queue_manager_thread = QueueManagerImpl(use_multiprocessing=False)
    assert isinstance(queue_manager_thread.control_queue, queue.Queue)
    assert isinstance(queue_manager_thread.completion_queue, queue.Queue)
    assert isinstance(queue_manager_thread.input_queue, queue.Queue)


@save_and_restore_main
def test_kernel_manager_run_mode() -> None:
    # Mock objects and data for testing
    queue_manager = QueueManagerImpl(use_multiprocessing=False)
    mode = SessionMode.RUN

    # Instantiate a KernelManager
    kernel_manager = KernelManagerImpl(
        queue_manager=queue_manager,
        mode=mode,
        configs={},
        app_metadata=app_metadata,
        config_manager=get_default_config_manager(current_path=None),
        virtual_files_supported=True,
        redirect_console_to_browser=False,
    )

    kernel_manager.start_kernel()

    # Assert startup
    assert kernel_manager.kernel_task is not None
    assert kernel_manager._read_conn is None
    assert kernel_manager.is_alive()

    kernel_manager.close_kernel()

    # Assert shutdown
    assert isinstance(kernel_manager.kernel_task, threading.Thread)
    kernel_manager.kernel_task.join()
    assert not kernel_manager.is_alive()
    assert queue_manager.input_queue.empty()
    assert queue_manager.control_queue.empty()


@save_and_restore_main
def test_kernel_manager_edit_mode() -> None:
    # Mock objects and data for testing
    queue_manager = QueueManagerImpl(use_multiprocessing=True)
    mode = SessionMode.EDIT

    # Instantiate a KernelManager
    kernel_manager = KernelManagerImpl(
        queue_manager=queue_manager,
        mode=mode,
        configs={},
        app_metadata=app_metadata,
        config_manager=get_default_config_manager(current_path=None),
        virtual_files_supported=True,
        redirect_console_to_browser=False,
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
def test_kernel_manager_interrupt(tmp_path: Path) -> None:
    queue_manager = QueueManagerImpl(use_multiprocessing=True)
    mode = SessionMode.EDIT

    kernel_manager = KernelManagerImpl(
        queue_manager=queue_manager,
        mode=mode,
        configs={},
        app_metadata=app_metadata,
        config_manager=get_default_config_manager(current_path=None),
        virtual_files_supported=True,
        redirect_console_to_browser=False,
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
        file = Path(
            "".join(random.choice(string.ascii_uppercase) for _ in range(10))
            + ".txt"
        )
    else:
        file = tmp_path / "output.txt"

    Path(file).write_text("-1")

    queue_manager.control_queue.put(
        CreationRequest(
            execution_requests=(
                ExecutionRequest(
                    cell_id="1",
                    code=inspect.cleandoc(
                        f"""
                            import time
                            with open("{file}", 'w') as f:
                                f.write('0')
                            time.sleep(2)
                            with open("{file}", 'w') as f:
                                f.write('1')
                            """
                    ),
                ),
            ),
            set_ui_element_value_request=SetUIElementValueRequest(
                object_ids=[], values=[]
            ),
            auto_run=True,
        )
    )

    timeout = 5
    # Wait for the file to be written to 0
    start_time = time.time()
    while time.time() < start_time + timeout / 2:
        time.sleep(0.1)
        if file.read_text() == "0":
            break
    kernel_manager.interrupt_kernel()

    try:
        assert file.read_text() == "0"
        # if kernel failed to interrupt, f will read as "1"
        time.sleep(1.5)
        assert file.read_text() == "0"
    finally:
        if sys.platform == "win32":
            os.remove(file)

        # Wait for queues to be empty with timeout
        # This makes the test more resilient to timing issues in CI
        start_time = time.time()
        timeout = 5  # 5-second timeout for queues to be empty

        # Give some time for queues to be processed first
        time.sleep(0.5)

        while time.time() - start_time < timeout:
            if (
                queue_manager.input_queue.empty()
                and queue_manager.control_queue.empty()
            ):
                break
            time.sleep(0.2)  # slightly longer interval

        # Now check if queues are empty
        assert queue_manager.input_queue.empty()
        assert queue_manager.control_queue.empty()

        # Assert shutdown
        kernel_manager.close_kernel()
        kernel_manager.kernel_task.join(timeout=5)
        assert not kernel_manager.is_alive()


session_id = SessionId("test_session_id")


@save_and_restore_main
async def test_session() -> None:
    session_consumer: Any = MagicMock()
    session_consumer.connection_state.return_value = ConnectionState.OPEN
    queue_manager = QueueManagerImpl(use_multiprocessing=False)
    kernel_manager = KernelManagerImpl(
        queue_manager=queue_manager,
        mode=SessionMode.RUN,
        configs={},
        app_metadata=app_metadata,
        config_manager=get_default_config_manager(current_path=None),
        virtual_files_supported=True,
        redirect_console_to_browser=False,
    )

    # Instantiate a Session
    session = SessionImpl(
        session_id,
        session_consumer,
        queue_manager,
        kernel_manager,
        AppFileManager.from_app(InternalApp(App())),
        get_default_config_manager(current_path=None),
        ttl_seconds=None,
        extensions=[],
    )

    # Assert startup
    assert session.room.main_consumer == session_consumer
    assert session._queue_manager == queue_manager
    assert session.kernel_manager == kernel_manager
    session_consumer.on_attach.assert_called_once()
    assert session_consumer.on_detach.call_count == 0
    assert session.connection_state() == ConnectionState.OPEN

    session.close()

    # Assert shutdown
    assert kernel_manager.kernel_task is not None
    kernel_manager.kernel_task.join()
    assert not kernel_manager.is_alive()
    assert queue_manager.input_queue.empty()
    assert queue_manager.control_queue.empty()
    session_consumer.on_attach.assert_called_once()
    session_consumer.on_detach.assert_called_once()
    assert session.connection_state() == ConnectionState.CLOSED


@save_and_restore_main
def test_session_disconnect_reconnect() -> None:
    session_consumer: Any = MagicMock()
    session_consumer.connection_state.return_value = ConnectionState.OPEN
    queue_manager = QueueManagerImpl(use_multiprocessing=False)
    kernel_manager = KernelManagerImpl(
        queue_manager=queue_manager,
        mode=SessionMode.RUN,
        configs={},
        app_metadata=app_metadata,
        config_manager=get_default_config_manager(current_path=None),
        virtual_files_supported=True,
        redirect_console_to_browser=False,
    )

    # Instantiate a Session
    session = SessionImpl(
        initialization_id=session_id,
        session_consumer=session_consumer,
        queue_manager=queue_manager,
        kernel_manager=kernel_manager,
        app_file_manager=AppFileManager.from_app(InternalApp(App())),
        config_manager=get_default_config_manager(current_path=None),
        ttl_seconds=None,
        extensions=[],
    )

    # Assert startup
    assert session.room.main_consumer == session_consumer
    session_consumer.on_attach.assert_called_once()
    assert session_consumer.on_detach.call_count == 0

    session.disconnect_consumer(session_consumer)

    # Assert shutdown of consumer
    assert session.room.main_consumer is None
    session_consumer.on_attach.assert_called_once()
    session_consumer.on_detach.assert_called_once()
    assert session.connection_state() == ConnectionState.ORPHANED

    # Reconnect
    new_session_consumer = MagicMock()
    session.connect_consumer(new_session_consumer, main=True)
    assert session.room.main_consumer == new_session_consumer
    new_session_consumer.on_attach.assert_called_once()
    assert new_session_consumer.on_detach.call_count == 0

    session.close()
    new_session_consumer.connection_state.return_value = ConnectionState.CLOSED

    # Assert shutdown
    assert kernel_manager.kernel_task is not None
    kernel_manager.kernel_task.join()
    assert not kernel_manager.is_alive()
    new_session_consumer.on_attach.assert_called_once()
    new_session_consumer.on_detach.assert_called_once()
    assert session.connection_state() == ConnectionState.CLOSED


@save_and_restore_main
def test_session_with_kiosk_consumers() -> None:
    session_consumer: Any = MagicMock()
    session_consumer.connection_state.return_value = ConnectionState.OPEN
    queue_manager = QueueManagerImpl(use_multiprocessing=False)
    kernel_manager = KernelManagerImpl(
        queue_manager=queue_manager,
        mode=SessionMode.RUN,
        configs={},
        app_metadata=app_metadata,
        config_manager=get_default_config_manager(current_path=None),
        virtual_files_supported=True,
        redirect_console_to_browser=False,
    )

    # Instantiate a Session
    session = SessionImpl(
        initialization_id=session_id,
        session_consumer=session_consumer,
        queue_manager=queue_manager,
        kernel_manager=kernel_manager,
        app_file_manager=AppFileManager.from_app(InternalApp(App())),
        config_manager=get_default_config_manager(current_path=None),
        ttl_seconds=None,
        extensions=[],
    )

    # Assert startup
    assert session.room.main_consumer == session_consumer
    assert session._queue_manager == queue_manager
    assert session.kernel_manager == kernel_manager
    session_consumer.on_attach.assert_called_once()
    assert session_consumer.on_detach.call_count == 0
    assert session.connection_state() == ConnectionState.OPEN

    # Create a kiosk consumer
    kiosk_consumer: Any = MagicMock()
    kiosk_consumer.connection_state.return_value = ConnectionState.OPEN
    session.connect_consumer(kiosk_consumer, main=False)

    # Assert startup of kiosk consumer
    assert session.room.main_consumer != kiosk_consumer
    assert kiosk_consumer in session.room.consumers
    kiosk_consumer.on_attach.assert_called_once()
    assert kiosk_consumer.on_detach.call_count == 0
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
    session_consumer.on_attach.assert_called_once()
    session_consumer.on_detach.assert_called_once()
    kiosk_consumer.on_attach.assert_called_once()
    kiosk_consumer.on_detach.assert_called_once()
    assert session.connection_state() == ConnectionState.CLOSED
    assert not session.room.consumers
    assert session.room.main_consumer is None


@pytest.mark.flaky(reruns=3)
@save_and_restore_main
async def test_session_manager_file_watching(tmp_path: Path) -> None:
    # Create a temporary file
    tmp_file = tmp_path / "test.py"
    # Write initial notebook content
    tmp_file.write_text(
        """import marimo
app = marimo.App()

@app.cell
def __():
    1
"""
    )
    file_key = str(tmp_file)

    try:
        # Create a session manager with file watching enabled
        file_router = AppFileRouter.from_filename(MarimoPath(tmp_file))
        session_manager = SessionManager(
            file_router=file_router,
            mode=SessionMode.EDIT,
            quiet=True,
            include_code=True,
            lsp_server=MagicMock(),
            config_manager=get_default_config_manager(
                current_path=None
            ).with_overrides(
                {
                    "runtime": {
                        "watcher_on_save": "lazy",
                    }
                }
            ),
            cli_args={},
            argv=None,
            auth_token=None,
            redirect_console_to_browser=False,
            ttl_seconds=None,
            watch=True,
        )

        session_consumer = MockSessionConsumer()

        # Create a session
        session_manager.create_session(
            session_id=session_id,
            session_consumer=session_consumer,
            query_params={},
            file_key=file_key,
            auto_instantiate=False,
        )

        # Wait a loop to ensure the session is created
        await asyncio.sleep(0.2)

        tmp_file.write_text(
            """import marimo
app = marimo.App()

@app.cell
def __():
    2
"""
        )

        # Wait for the watcher to detect the change
        for _ in range(16):  # noqa: B007
            await asyncio.sleep(0.1)
            if len(session_consumer.notify_calls) > 0:
                break

        # Check that UpdateCellCodes was sent with the new code
        update_ops = [
            op
            for op in session_consumer.notify_calls
            if isinstance(op, UpdateCellCodesNotification)
        ]
        assert len(update_ops) == 1
        assert "2" == update_ops[0].codes[0]
        assert update_ops[0].code_is_stale is True

        # Create another session for the same file
        session_consumer2 = MockSessionConsumer()
        session_manager.create_session(
            session_id=SessionId("test2"),
            session_consumer=session_consumer2,
            query_params={},
            file_key=file_key,
            auto_instantiate=False,
        )

        # Modify the file again
        session_consumer.notify_calls.clear()
        session_consumer2.notify_calls.clear()
        tmp_file.write_text(
            """import marimo
app = marimo.App()

@app.cell
def __():
    3
"""
        )

        # Wait for the watcher to detect the change
        for _ in range(16):  # noqa: B007
            await asyncio.sleep(0.1)
            if len(session_consumer.notify_calls) > 0:
                break

        # Both sessions should receive the update
        update_ops = [
            op
            for op in session_consumer.notify_calls
            if isinstance(op, UpdateCellCodesNotification)
        ]
        update_ops2 = [
            op
            for op in session_consumer2.notify_calls
            if isinstance(op, UpdateCellCodesNotification)
        ]
        assert len(update_ops) == 1
        assert len(update_ops2) == 1
        assert "3" == update_ops[0].codes[0]
        assert "3" == update_ops2[0].codes[0]

        # Close one session and verify the other still receives updates
        session_manager.close_session(session_id)
        session_consumer.notify_calls.clear()
        session_consumer2.notify_calls.clear()

        tmp_file.write_text(
            """import marimo
app = marimo.App()

@app.cell
def __():
    4
"""
        )

        # Wait for the watcher to detect the change
        for _ in range(16):  # noqa: B007
            await asyncio.sleep(0.1)
            if len(session_consumer2.notify_calls) > 0:
                break

        # Only one session should receive the update
        update_ops2 = [
            op
            for op in session_consumer2.notify_calls
            if isinstance(op, UpdateCellCodesNotification)
        ]
        assert len(update_ops2) == 1
        assert "4" == update_ops2[0].codes[0]
    finally:
        # Cleanup
        session_manager.shutdown()


@save_and_restore_main
def test_watch_mode_does_not_override_config(tmp_path: Path) -> None:
    """Test that watch mode does not override config settings."""
    # Create a temporary file
    tmp_file = tmp_path / "test_watch_mode_config_override.py"
    tmp_file.write_text("import marimo as mo")

    # Create a default config (autosave enabled by default)
    config_reader = get_default_config_manager(current_path=None)

    # Create a session manager with watch mode enabled
    file_router = AppFileRouter.from_filename(MarimoPath(str(tmp_file)))
    session_manager = SessionManager(
        file_router=file_router,
        mode=SessionMode.EDIT,
        quiet=True,
        include_code=True,
        lsp_server=MagicMock(),
        config_manager=config_reader,
        cli_args={},
        argv=None,
        auth_token=None,
        redirect_console_to_browser=False,
        ttl_seconds=None,
        watch=True,
    )

    session_manager_no_watch = SessionManager(
        file_router=file_router,
        mode=SessionMode.EDIT,
        quiet=True,
        include_code=True,
        lsp_server=MagicMock(),
        config_manager=config_reader,
        cli_args={},
        argv=None,
        auth_token=None,
        redirect_console_to_browser=False,
        ttl_seconds=None,
        watch=False,
    )

    try:
        # Verify that the config was not overridden for watch mode
        config = session_manager._config_manager.get_config()
        assert config["save"]["autosave"] == "after_delay"
        assert config["save"]["format_on_save"] is True

    finally:
        # Cleanup
        session_manager.shutdown()
        session_manager_no_watch.shutdown()


@pytest.mark.flaky(reruns=3)
@save_and_restore_main
async def test_watch_mode_with_watcher_on_save_autorun(tmp_path: Path) -> None:
    """Test that watch mode with autorun config auto-executes changed cells."""
    tmp_file = tmp_path / "test.py"
    tmp_file.write_text(
        dedent(
            """
        import marimo
        app = marimo.App()

        @app.cell
        def __():
            1
        """
        )
    )
    session_manager: SessionManager | None = None

    try:
        # Create a config with watcher_on_save set to autorun
        config_reader = get_default_config_manager(current_path=None)
        config_reader_autorun = config_reader.with_overrides(
            {
                "runtime": {
                    "watcher_on_save": "autorun",
                }
            }
        )

        # Create a session manager with file watching enabled
        file_router = AppFileRouter.from_filename(MarimoPath(str(tmp_file)))
        session_manager = SessionManager(
            file_router=file_router,
            mode=SessionMode.EDIT,
            quiet=True,
            include_code=True,
            lsp_server=MagicMock(),
            config_manager=config_reader_autorun,
            cli_args={},
            argv=None,
            auth_token=None,
            redirect_console_to_browser=False,
            ttl_seconds=None,
            watch=True,
        )

        # Create a mock session consumer
        session_consumer = MockSessionConsumer()

        # Create a session
        session = session_manager.create_session(
            session_id=session_id,
            session_consumer=session_consumer,
            query_params={},
            file_key=str(tmp_file),
            auto_instantiate=False,
        )
        session.session_view = MagicMock(SessionView)

        # Wait for file watcher to be initialized by checking it exists
        for _ in range(20):  # noqa: B007
            await asyncio.sleep(0.05)
            if (
                hasattr(session_manager, "_file_watcher")
                and session_manager._file_watcher is not None
            ):
                break

        # Modify the file
        session_consumer.notify_calls.clear()
        tmp_file.write_text(
            dedent(
                """
            import marimo
            app = marimo.App()

            @app.cell
            def __():
                2
            """
            )
        )

        # Wait for the watcher to detect the change and send UpdateCellCodes
        update_ops: list[UpdateCellCodesNotification] = []
        for _ in range(20):  # noqa: B007
            await asyncio.sleep(0.1)
            update_ops = [
                op
                for op in session_consumer.notify_calls
                if isinstance(op, UpdateCellCodesNotification)
            ]
            if update_ops:
                break

        # Check that UpdateCellCodes was sent with code_is_stale=False (autorun)
        assert len(update_ops) == 1
        assert "2" in update_ops[0].codes[0]
        assert update_ops[0].code_is_stale is False

        # Verify that cells were queued for execution
        assert session.session_view.add_control_request.called
        last_call = session.session_view.add_control_request.call_args[0][0]
        assert isinstance(last_call, SyncGraphRequest)

    finally:
        # Cleanup
        if session_manager:
            session_manager.shutdown()


@save_and_restore_main
async def test_watch_mode_with_watcher_on_save_lazy(tmp_path: Path) -> None:
    """Test that watch mode with lazy config marks cells as stale without executing."""
    tmp_file = tmp_path / "test.py"
    tmp_file.write_text(
        dedent(
            """
        import marimo
        app = marimo.App()

        @app.cell
        def __():
            1
        """
        )
    )
    session_manager: SessionManager | None = None

    try:
        # Create a config with watcher_on_save set to lazy
        config_reader = get_default_config_manager(current_path=None)
        config_reader_lazy = config_reader.with_overrides(
            {
                "runtime": {
                    "watcher_on_save": "lazy",
                }
            }
        )

        # Create a session manager with file watching enabled
        file_router = AppFileRouter.from_filename(MarimoPath(str(tmp_file)))
        session_manager = SessionManager(
            file_router=file_router,
            mode=SessionMode.EDIT,
            quiet=True,
            include_code=True,
            lsp_server=MagicMock(),
            config_manager=config_reader_lazy,
            cli_args={},
            argv=None,
            auth_token=None,
            redirect_console_to_browser=False,
            ttl_seconds=None,
            watch=True,
        )

        # Create a mock session consumer
        session_consumer = MockSessionConsumer()

        # Create a session
        session = session_manager.create_session(
            session_id=session_id,
            session_consumer=session_consumer,
            query_params={},
            file_key=str(tmp_file),
            auto_instantiate=False,
        )

        # Wait a bit for session to be ready
        for _ in range(16):  # noqa: B007
            await asyncio.sleep(0.1)
            if len(session_consumer.notify_calls) > 0:
                break

        # Modify the file
        session_consumer.notify_calls.clear()
        tmp_file.write_text(
            dedent(
                """
            import marimo
            app = marimo.App()

            @app.cell
            def __():
                2
            """
            )
        )

        # Wait for the watcher to detect the change
        for _ in range(16):  # noqa: B007
            await asyncio.sleep(0.1)
            if len(session_consumer.notify_calls) > 0:
                break

        # Check that UpdateCellCodes was sent with code_is_stale=True (lazy)
        update_ops = [
            op
            for op in session_consumer.notify_calls
            if isinstance(op, UpdateCellCodesNotification)
        ]
        assert len(update_ops) == 1
        assert "2" in update_ops[0].codes[0]
        assert update_ops[0].code_is_stale is True

    finally:
        # Cleanup
        if session_manager:
            session_manager.shutdown()


@save_and_restore_main
async def test_session_manager_file_rename() -> None:
    """Test that file renaming works correctly with file watching."""
    # Create two temporary files
    with (
        NamedTemporaryFile(delete=False, suffix=".py") as tmp_file1,
    ):
        tmp_path1 = Path(tmp_file1.name)
        # Write initial notebook content
        tmp_file1.write(
            b"""import marimo
app = marimo.App()

@app.cell
def __():
    1
"""
        )

    new_path = tmp_path1.with_suffix(".1.py")

    try:
        # Create a session manager with file watching enabled
        file_router = AppFileRouter.from_filename(MarimoPath(str(tmp_path1)))
        session_manager = SessionManager(
            file_router=file_router,
            mode=SessionMode.EDIT,
            quiet=True,
            include_code=True,
            lsp_server=MagicMock(),
            config_manager=get_default_config_manager(current_path=None),
            cli_args={},
            argv=None,
            auth_token=None,
            redirect_console_to_browser=False,
            ttl_seconds=None,
            watch=True,
        )

        # Create a mock session consumer
        session_consumer = MagicMock()
        session_consumer.connection_state.return_value = ConnectionState.OPEN
        operations: list[Any] = []
        session_consumer.notify = lambda op, *_args: operations.append(
            deserialize_kernel_message(op)
        )

        # Create a session
        session_manager.create_session(
            session_id=session_id,
            session_consumer=session_consumer,
            query_params={},
            file_key=str(tmp_path1),
            auto_instantiate=False,
        )

        # Try to rename to a non-existent file
        success, error = await session_manager.rename_session(
            session_id, "/nonexistent/file.py"
        )
        assert not success
        assert error is not None
        assert "Failed to rename" in error

        # Try to rename with an invalid session
        success, error = await session_manager.rename_session(
            "nonexistent", str(new_path)
        )
        assert not success
        assert error is not None
        assert "Session not found" in error

        # Rename to the second file
        session = session_manager.get_session(session_id)
        assert session is not None
        session.app_file_manager.rename(str(new_path))
        assert new_path.exists()
        success, error = await session_manager.rename_session(
            session_id, str(new_path)
        )
        assert success
        assert error is None

        # Modify the new file
        operations.clear()
        new_path.write_text(
            """import marimo
app = marimo.App()

@app.cell
def __():
    2
"""
        )

        # Wait for the watcher to detect the change
        for _ in range(16):  # noqa: B007
            await asyncio.sleep(0.1)
            if len(operations) > 0:
                break

        # Check that UpdateCellCodes was sent with the new code
        update_ops = [
            op
            for op in operations
            if isinstance(op, UpdateCellCodesNotification)
        ]
        assert len(update_ops) == 1
        assert "2" == update_ops[0].codes[0]

    finally:
        # Cleanup
        session_manager.shutdown()
        if new_path.exists():  # noqa: ASYNC240
            os.remove(new_path)
        if tmp_path1.exists():  # noqa: ASYNC240
            os.remove(tmp_path1)


@save_and_restore_main
def test_session_with_script_config_overrides(
    tmp_path: Path,
) -> None:
    session_consumer = MagicMock()
    session_consumer.connection_state.return_value = ConnectionState.OPEN

    # Create a temporary file with script config
    tmp_file = tmp_path / "test_script_config.py"
    tmp_file.write_text(
        dedent(
            """
        # /// script
        # [tool.marimo.formatting]
        # line_length = 999
        # ///
        """
        )
    )

    # Create app file manager with the temp file
    app_file_manager = AppFileManager(filename=str(tmp_file))

    # Create session with the file that has script config
    session = SessionImpl.create(
        initialization_id="test_id",
        session_consumer=session_consumer,
        mode=SessionMode.RUN,
        app_metadata=app_metadata,
        app_file_manager=app_file_manager,
        config_manager=get_default_config_manager(current_path=None),
        virtual_files_supported=True,
        redirect_console_to_browser=False,
        ttl_seconds=None,
        auto_instantiate=True,
    )

    # Verify that the session's config is affected by the script config
    assert (
        session.config_manager.get_config()["formatting"]["line_length"] == 999
    )
    assert (
        session.kernel_manager.config_manager.get_config()["formatting"][
            "line_length"
        ]
        == 999
    )

    # Cleanup
    session.close()
