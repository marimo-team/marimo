# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import functools
import inspect
import os
import queue
import sys
import time
from multiprocessing.queues import Queue as MPQueue
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, TypeVar
from unittest.mock import MagicMock

import pytest

from marimo._ast.app import App, InternalApp
from marimo._config.manager import get_default_config_manager
from marimo._messaging.ops import UpdateCellCodes
from marimo._runtime.requests import (
    AppMetadata,
    CreationRequest,
    ExecuteMultipleRequest,
    ExecutionRequest,
    SetUIElementValueRequest,
)
from marimo._server.file_manager import AppFileManager
from marimo._server.file_router import AppFileRouter
from marimo._server.model import ConnectionState, SessionMode
from marimo._server.session.session_view import SessionView
from marimo._server.sessions import (
    KernelManager,
    QueueManager,
    Session,
    SessionManager,
)
from marimo._server.utils import initialize_asyncio
from marimo._types.ids import SessionId
from marimo._utils.marimo_path import MarimoPath

initialize_asyncio()

F = TypeVar("F", bound=Callable[..., Any])

app_metadata = AppMetadata(
    query_params={"some_param": "some_value"}, filename="test.py", cli_args={}
)


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
        redirect_console_to_browser=False,
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
    queue_manager = QueueManager(use_multiprocessing=True)
    mode = SessionMode.EDIT

    kernel_manager = KernelManager(
        queue_manager,
        mode,
        {},
        app_metadata,
        get_default_config_manager(current_path=None),
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


@save_and_restore_main
async def test_session() -> None:
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
        redirect_console_to_browser=False,
    )

    # Instantiate a Session
    session = Session(
        session_id,
        session_consumer,
        queue_manager,
        kernel_manager,
        AppFileManager.from_app(InternalApp(App())),
        ttl_seconds=None,
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
        redirect_console_to_browser=False,
    )

    # Instantiate a Session
    session = Session(
        session_id,
        session_consumer,
        queue_manager,
        kernel_manager,
        AppFileManager.from_app(InternalApp(App())),
        ttl_seconds=None,
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
        redirect_console_to_browser=False,
    )

    # Instantiate a Session
    session = Session(
        session_id,
        session_consumer,
        queue_manager,
        kernel_manager,
        AppFileManager.from_app(InternalApp(App())),
        ttl_seconds=None,
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


@pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="This test is flaky on Python 3.9",
)
@save_and_restore_main
async def test_session_manager_file_watching() -> None:
    # Create a temporary file
    with NamedTemporaryFile(delete=False, suffix=".py") as tmp_file:
        tmp_path = Path(tmp_file.name)
        # Write initial notebook content
        tmp_file.write(
            b"""import marimo
app = marimo.App()

@app.cell
def __():
    1
"""
        )

    try:
        # Create a session manager with file watching enabled
        file_router = AppFileRouter.from_filename(MarimoPath(str(tmp_path)))
        session_manager = SessionManager(
            file_router=file_router,
            mode=SessionMode.EDIT,
            development_mode=False,
            quiet=True,
            include_code=True,
            lsp_server=MagicMock(),
            user_config_manager=get_default_config_manager(
                current_path=None
            ).with_overrides(
                {
                    "runtime": {
                        "watcher_on_save": "lazy",
                    }
                }
            ),
            cli_args={},
            auth_token=None,
            redirect_console_to_browser=False,
            ttl_seconds=None,
            watch=True,
        )

        # Create a mock session consumer
        session_consumer = MagicMock()
        session_consumer.connection_state.return_value = ConnectionState.OPEN
        operations: list[Any] = []
        session_consumer.write_operation = (
            lambda op, *_args: operations.append(op)
        )

        # Create a session
        session_manager.create_session(
            session_id=session_id,
            session_consumer=session_consumer,
            query_params={},
            file_key=str(tmp_path),
        )

        tmp_path.write_text(
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
            op for op in operations if isinstance(op, UpdateCellCodes)
        ]
        assert len(update_ops) == 1
        assert "2" == update_ops[0].codes[0]
        assert update_ops[0].code_is_stale is True

        # Create another session for the same file
        session_consumer2 = MagicMock()
        session_consumer2.connection_state.return_value = ConnectionState.OPEN
        operations2: list[Any] = []
        session_consumer2.write_operation = (
            lambda op, *_args: operations2.append(op)
        )

        session_manager.create_session(
            session_id=SessionId("test2"),
            session_consumer=session_consumer2,
            query_params={},
            file_key=str(tmp_path),
        )

        # Modify the file again
        operations.clear()
        operations2.clear()
        tmp_path.write_text(
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
            if len(operations) > 0:
                break

        # Both sessions should receive the update
        update_ops = [
            op for op in operations if isinstance(op, UpdateCellCodes)
        ]
        update_ops2 = [
            op for op in operations2 if isinstance(op, UpdateCellCodes)
        ]
        assert len(update_ops) == 1
        assert len(update_ops2) == 1
        assert "3" == update_ops[0].codes[0]
        assert "3" == update_ops2[0].codes[0]

        # Close one session and verify the other still receives updates
        session_manager.close_session(session_id)
        operations.clear()
        operations2.clear()

        tmp_path.write_text(
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
            if len(operations2) > 0:
                break

        # Only one session should receive the update
        update_ops2 = [
            op for op in operations2 if isinstance(op, UpdateCellCodes)
        ]
        assert len(update_ops2) == 1
        assert "4" == update_ops2[0].codes[0]
    finally:
        # Cleanup
        session_manager.shutdown()
        os.remove(tmp_path)


@save_and_restore_main
def test_watch_mode_config_override() -> None:
    """Test that watch mode properly overrides config settings."""
    # Create a temporary file
    with NamedTemporaryFile(delete=False, suffix=".py") as tmp_file:
        tmp_path = Path(tmp_file.name)
        tmp_file.write(b"import marimo as mo")

    # Create a config with autosave enabled
    config_reader = get_default_config_manager(current_path=None)
    config_reader_watch = config_reader.with_overrides(
        {
            "save": {
                "autosave": "off",
                "format_on_save": False,
                "autosave_delay": 2000,
            }
        }
    )

    # Create a session manager with watch mode enabled
    file_router = AppFileRouter.from_filename(MarimoPath(str(tmp_path)))
    session_manager = SessionManager(
        file_router=file_router,
        mode=SessionMode.EDIT,
        development_mode=False,
        quiet=True,
        include_code=True,
        lsp_server=MagicMock(),
        user_config_manager=config_reader_watch,
        cli_args={},
        auth_token=None,
        redirect_console_to_browser=False,
        ttl_seconds=None,
        watch=True,
    )

    session_manager_no_watch = SessionManager(
        file_router=file_router,
        mode=SessionMode.EDIT,
        development_mode=False,
        quiet=True,
        include_code=True,
        lsp_server=MagicMock(),
        user_config_manager=config_reader,
        cli_args={},
        auth_token=None,
        redirect_console_to_browser=False,
        ttl_seconds=None,
        watch=False,
    )

    try:
        # Verify that the config was overridden
        config = session_manager.user_config_manager.get_config()
        assert config["save"]["autosave"] == "off"
        assert config["save"]["format_on_save"] is False

        # Verify that the config was not overridden
        config = session_manager_no_watch.user_config_manager.get_config()
        assert config["save"]["autosave"] == "after_delay"
        assert config["save"]["format_on_save"] is True

    finally:
        # Cleanup
        session_manager.shutdown()
        session_manager_no_watch.shutdown()
        os.remove(tmp_path)


@pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="This test is flaky on Python 3.9",
)
@save_and_restore_main
async def test_watch_mode_with_watcher_on_save_config() -> None:
    """Test that watch mode works correctly with watcher_on_save config."""
    # Create a temporary file
    with NamedTemporaryFile(delete=False, suffix=".py") as tmp_file:
        tmp_path = Path(tmp_file.name)
        # Write initial notebook content
        tmp_file.write(
            b"""import marimo
app = marimo.App()

@app.cell
def __():
    1
"""
        )

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
        file_router = AppFileRouter.from_filename(MarimoPath(str(tmp_path)))
        session_manager = SessionManager(
            file_router=file_router,
            mode=SessionMode.EDIT,
            development_mode=False,
            quiet=True,
            include_code=True,
            lsp_server=MagicMock(),
            user_config_manager=config_reader_autorun,
            cli_args={},
            auth_token=None,
            redirect_console_to_browser=False,
            ttl_seconds=None,
            watch=True,
        )

        # Create a mock session consumer
        session_consumer = MagicMock()
        session_consumer.connection_state.return_value = ConnectionState.OPEN
        operations: list[Any] = []
        session_consumer.write_operation = (
            lambda op, *_args: operations.append(op)
        )

        # Create a session
        session = session_manager.create_session(
            session_id=session_id,
            session_consumer=session_consumer,
            query_params={},
            file_key=str(tmp_path),
        )
        session.session_view = MagicMock(SessionView)

        # Wait a bit and then modify the file
        for _ in range(16):  # noqa: B007
            await asyncio.sleep(0.1)
            if len(operations) > 0:
                break

        # Modify the file
        operations.clear()
        with open(tmp_path, "w") as f:  # noqa: ASYNC230
            f.write(
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

        # Check that UpdateCellCodes was sent with code_is_stale=False (autorun)
        update_ops = [
            op for op in operations if isinstance(op, UpdateCellCodes)
        ]
        assert len(update_ops) == 1
        assert "2" in update_ops[0].codes[0]
        assert update_ops[0].code_is_stale is False

        # Verify that cells were queued for execution
        assert session.session_view.add_control_request.called
        last_call = session.session_view.add_control_request.call_args[0][0]
        assert isinstance(last_call, ExecuteMultipleRequest)

        # Now change config to lazy mode
        config_reader_lazy = config_reader.with_overrides(
            {
                "runtime": {
                    "watcher_on_save": "lazy",
                }
            }
        )
        session_manager.user_config_manager = config_reader_lazy

        # Reset the mock
        session_consumer.put_control_request.reset_mock()

        # Modify the file again
        operations.clear()
        with open(tmp_path, "w") as f:  # noqa: ASYNC230
            f.write(
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
            if len(operations) > 0:
                break

        # Check that UpdateCellCodes was sent with code_is_stale=True (lazy)
        update_ops = [
            op for op in operations if isinstance(op, UpdateCellCodes)
        ]
        assert len(update_ops) == 1
        assert "3" in update_ops[0].codes[0]
        assert update_ops[0].code_is_stale is True

        # Verify that no execution was queued
        assert not session_consumer.put_control_request.called

    finally:
        # Cleanup
        session_manager.shutdown()
        os.remove(tmp_path)


@pytest.mark.skipif(
    sys.version_info < (3, 10),
    reason="This test is flaky on Python 3.9",
)
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
            development_mode=False,
            quiet=True,
            include_code=True,
            lsp_server=MagicMock(),
            user_config_manager=get_default_config_manager(current_path=None),
            cli_args={},
            auth_token=None,
            redirect_console_to_browser=False,
            ttl_seconds=None,
            watch=True,
        )

        # Create a mock session consumer
        session_consumer = MagicMock()
        session_consumer.connection_state.return_value = ConnectionState.OPEN
        operations: list[Any] = []
        session_consumer.write_operation = (
            lambda op, *_args: operations.append(op)
        )

        # Create a session
        session_manager.create_session(
            session_id=session_id,
            session_consumer=session_consumer,
            query_params={},
            file_key=str(tmp_path1),
        )

        # Try to rename to a non-existent file
        success, error = session_manager.handle_file_rename_for_watch(
            session_id, str(tmp_path1), "/nonexistent/file.py"
        )
        assert not success
        assert error is not None
        assert "does not exist" in error

        # Try to rename with an invalid session
        success, error = session_manager.handle_file_rename_for_watch(
            "nonexistent", str(tmp_path1), str(new_path)
        )
        assert not success
        assert error is not None
        assert "Session not found" in error

        # Rename to the second file
        session = session_manager.get_session(session_id)
        assert session is not None
        session.app_file_manager.rename(str(new_path))
        assert new_path.exists()
        success, error = session_manager.handle_file_rename_for_watch(
            session_id, str(tmp_path1), str(new_path)
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
            op for op in operations if isinstance(op, UpdateCellCodes)
        ]
        assert len(update_ops) == 1
        assert "2" == update_ops[0].codes[0]

    finally:
        # Cleanup
        session_manager.shutdown()
        os.remove(new_path)


@save_and_restore_main
async def test_sync_session_view_from_cache(tmp_path: Path) -> None:
    """Test syncing session view from cache."""
    # Create a temporary file
    notebook_path = tmp_path / "test.py"
    notebook_path.write_text(
        """import marimo

app = marimo.App()

@app.cell
def __():
    1
"""
    )

    # Create session with the temporary file
    session_consumer = MagicMock()
    session_consumer.connection_state.return_value = ConnectionState.OPEN
    queue_manager = QueueManager(use_multiprocessing=False)
    kernel_manager = KernelManager(
        queue_manager,
        SessionMode.RUN,
        {},
        app_metadata,
        get_default_config_manager(current_path=None),
        virtual_files_supported=True,
        redirect_console_to_browser=False,
    )

    app_file_manager = AppFileManager(filename=str(notebook_path))
    session = Session(
        session_id,
        session_consumer,
        queue_manager,
        kernel_manager,
        app_file_manager,
        ttl_seconds=None,
    )

    # Test syncing when no cache exists
    session.sync_session_view_from_cache()
    # Should create a new empty session view since no cache exists
    assert session.session_view is not None
    assert session.session_cache_manager is not None
    assert session.session_cache_manager.path == str(notebook_path)
    assert (
        session.session_cache_manager.interval
        == Session.SESSION_CACHE_INTERVAL_SECONDS
    )

    # Add some operations to the session view
    session.write_operation(
        UpdateCellCodes(
            cell_ids=["1"],
            codes=["print('hello')"],
            code_is_stale=False,
        ),
        from_consumer_id=None,
    )

    # Create a new session and sync from cache
    session2 = Session(
        "test2",
        session_consumer,
        queue_manager,
        kernel_manager,
        app_file_manager,
        ttl_seconds=None,
    )
    session2.sync_session_view_from_cache()

    # Verify the session views match
    assert session2.session_view is not None
    assert session2.session_cache_manager is not None
    assert session2.session_cache_manager.path == str(notebook_path)
    assert len(session2.session_view.operations) == len(
        session.session_view.operations
    )

    # Test syncing with no file path
    app_file_manager_no_path = AppFileManager.from_app(InternalApp(App()))
    session3 = Session(
        "test3",
        session_consumer,
        queue_manager,
        kernel_manager,
        app_file_manager_no_path,
        ttl_seconds=None,
    )
    session3.sync_session_view_from_cache()
    # Should create a new empty session view since no path exists
    assert session3.session_view is not None
    assert session3.session_cache_manager is not None
    assert session3.session_cache_manager.path is None

    # Cleanup
    session.close()
    session2.close()
    session3.close()
    if kernel_manager.kernel_task:
        kernel_manager.kernel_task.join()
