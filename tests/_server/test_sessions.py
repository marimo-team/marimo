# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import contextlib
import inspect
import os
import queue
import signal
import sys
import threading
import time
from multiprocessing.queues import Queue as MPQueue
from pathlib import Path
from tempfile import NamedTemporaryFile
from textwrap import dedent
from typing import Any
from unittest.mock import MagicMock

import pytest

from marimo._ast.app import App, InternalApp
from marimo._ast.app_config import _AppConfig
from marimo._config.manager import (
    get_default_config_manager,
)
from marimo._messaging.errors import MarimoInterruptionError
from marimo._messaging.notification import (
    CellNotification,
    CompletedRunNotification,
    NotebookDocumentTransactionNotification,
    NotificationMessage,
)
from marimo._messaging.serde import deserialize_kernel_message
from marimo._messaging.types import KernelMessage
from marimo._runtime.commands import (
    AppMetadata,
    CreateNotebookCommand,
    ExecuteCellCommand,
    SyncGraphCommand,
    UpdateUIElementCommand,
)
from marimo._server.session_manager import SessionManager
from marimo._server.utils import initialize_asyncio
from marimo._server.workspace import SingleFileWorkspace
from marimo._session import Session
from marimo._session.consumer import SessionConsumer
from marimo._session.events import SessionEventBus
from marimo._session.managers import (
    KernelManagerImpl,
    QueueManagerImpl,
)
from marimo._session.model import ConnectionState, SessionMode
from marimo._session.notebook import AppFileManager
from marimo._session.session import (
    SessionImpl,
)
from marimo._session.startup import SessionStartup
from marimo._session.state.session_view import SessionView
from marimo._types.ids import ConsumerId, SessionId
from marimo._utils.marimo_path import MarimoPath

initialize_asyncio()


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


session_id = SessionId("test")


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


async def test_kernel_manager_run_mode() -> None:
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
        virtual_file_storage="in_memory",
        redirect_console_to_browser=False,
    )

    await kernel_manager.start_kernel()

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


async def test_kernel_manager_edit_mode() -> None:
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
        virtual_file_storage="shared_memory",
        redirect_console_to_browser=False,
    )

    await kernel_manager.start_kernel()

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


async def test_kernel_manager_interrupt() -> None:
    queue_manager = QueueManagerImpl(use_multiprocessing=True)
    kernel_manager = KernelManagerImpl(
        queue_manager=queue_manager,
        mode=SessionMode.EDIT,
        configs={},
        app_metadata=app_metadata,
        config_manager=get_default_config_manager(current_path=None),
        virtual_file_storage="shared_memory",
        redirect_console_to_browser=False,
    )
    await kernel_manager.start_kernel()

    def interrupt_running_cell() -> bool:
        interrupted = False
        while True:
            message = deserialize_kernel_message(
                kernel_manager.kernel_connection.recv()
            )
            if isinstance(message, CompletedRunNotification):
                return interrupted
            if (
                not isinstance(message, CellNotification)
                or message.output is None
            ):
                continue
            output = message.output.data
            if isinstance(output, str) and "ready-to-interrupt" in output:
                kernel_manager.interrupt_kernel()
            elif isinstance(output, list):
                interrupted |= any(
                    isinstance(error, MarimoInterruptionError)
                    for error in output
                )

    try:
        queue_manager.put_control_request(
            CreateNotebookCommand(
                execution_requests=(
                    ExecuteCellCommand(
                        cell_id="1",
                        code=inspect.cleandoc("""
                            import marimo as mo
                            mo.output.append("ready-to-interrupt")
                            while True:
                                pass
                        """),
                    ),
                ),
                cell_ids=("1",),
                set_ui_element_value_request=UpdateUIElementCommand(
                    object_ids=[], values=[]
                ),
                auto_run=True,
            )
        )
        assert await asyncio.wait_for(
            asyncio.to_thread(interrupt_running_cell), timeout=5
        )
    finally:
        kernel_manager.close_kernel()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="interrupts don't reach subprocesses on Windows",
)
async def test_kernel_manager_interrupt_reaches_subprocesses(
    tmp_path: Path,
) -> None:
    queue_manager = QueueManagerImpl(use_multiprocessing=True)
    kernel_manager = KernelManagerImpl(
        queue_manager=queue_manager,
        mode=SessionMode.EDIT,
        configs={},
        app_metadata=app_metadata,
        config_manager=get_default_config_manager(current_path=None),
        virtual_file_storage="shared_memory",
        redirect_console_to_browser=False,
    )

    await kernel_manager.start_kernel()
    assert kernel_manager.kernel_task is not None
    assert kernel_manager.is_alive()

    pid_file = tmp_path / "pids.txt"
    queue_manager.control_queue.put(
        CreateNotebookCommand(
            execution_requests=(
                ExecuteCellCommand(
                    cell_id="1",
                    code=inspect.cleandoc(
                        f"""
                        import os
                        import subprocess
                        child = subprocess.Popen(["sleep", "600"])
                        detached = subprocess.Popen(
                            ["sleep", "600"], start_new_session=True
                        )
                        with open("{pid_file}.tmp", 'w') as f:
                            f.write(str(child.pid) + " " + str(detached.pid))
                        os.replace("{pid_file}.tmp", "{pid_file}")
                        child.wait()
                        """
                    ),
                ),
            ),
            cell_ids=("1",),
            set_ui_element_value_request=UpdateUIElementCommand(
                object_ids=[], values=[]
            ),
            auto_run=True,
        )
    )

    # Wait for the cell to report the pids of the two subprocesses. The
    # cell moves the fully written file into place, so existence implies
    # complete contents.
    child_pid = detached_pid = -1
    deadline = time.time() + 30
    while time.time() < deadline:
        if pid_file.exists():
            child_pid, detached_pid = (
                int(pid) for pid in pid_file.read_text().split()
            )
            break
        await asyncio.sleep(0.1)

    def terminated(pid: int) -> bool:
        # An interrupted child of the kernel may linger as a zombie until
        # the kernel reaps it; gone and zombie both count as terminated.
        import psutil

        try:
            return psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return True

    try:
        assert child_pid > 0
        assert detached_pid > 0
        kernel_manager.interrupt_kernel()

        deadline = time.time() + 10
        while time.time() < deadline and not terminated(child_pid):  # noqa: ASYNC110
            await asyncio.sleep(0.1)
        # The interrupt reaches subprocesses in the kernel's process group
        assert terminated(child_pid)
        # ... but spares subprocesses that detached into their own session
        assert not terminated(detached_pid)
        # ... and the kernel itself survives to serve future runs
        assert kernel_manager.is_alive()
    finally:
        for pid in (child_pid, detached_pid):
            if pid > 0:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(pid, signal.SIGKILL)
        kernel_manager.close_kernel()
        kernel_manager.kernel_task.join(timeout=5)
        assert not kernel_manager.is_alive()


session_id = SessionId("test_session_id")


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
        virtual_file_storage="in_memory",
        redirect_console_to_browser=False,
    )

    await kernel_manager.start_kernel()

    # Instantiate a Session
    session = SessionImpl(
        session_view=SessionView(),
        initialization_id=session_id,
        session_consumer=session_consumer,
        kernel_manager=kernel_manager,
        app_file_manager=AppFileManager.from_app(InternalApp(App())),
        config_manager=get_default_config_manager(current_path=None),
        ttl_seconds=None,
        extensions=[],
    )

    # Assert startup
    assert session.room.main_consumer == session_consumer
    assert session._kernel_manager == kernel_manager
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


def test_sessions_for_same_file_have_distinct_stable_ids() -> None:
    sessions = [
        SessionImpl(
            session_view=SessionView(),
            initialization_id="notebook.py",
            session_consumer=MagicMock(),
            kernel_manager=MagicMock(spec=KernelManagerImpl),
            app_file_manager=AppFileManager.from_app(InternalApp(App())),
            config_manager=get_default_config_manager(current_path=None),
            ttl_seconds=None,
            extensions=[],
        )
        for _ in range(2)
    ]
    try:
        assert sessions[0].stable_id != sessions[1].stable_id
    finally:
        for session in sessions:
            session.close()


async def test_session_disconnect_reconnect() -> None:
    session_consumer: Any = MagicMock()
    session_consumer.connection_state.return_value = ConnectionState.OPEN
    queue_manager = QueueManagerImpl(use_multiprocessing=False)
    kernel_manager = KernelManagerImpl(
        queue_manager=queue_manager,
        mode=SessionMode.RUN,
        configs={},
        app_metadata=app_metadata,
        config_manager=get_default_config_manager(current_path=None),
        virtual_file_storage="in_memory",
        redirect_console_to_browser=False,
    )

    await kernel_manager.start_kernel()

    # Instantiate a Session
    session = SessionImpl(
        session_view=SessionView(),
        initialization_id=session_id,
        session_consumer=session_consumer,
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


async def test_session_with_kiosk_consumers() -> None:
    session_consumer: Any = MagicMock()
    session_consumer.connection_state.return_value = ConnectionState.OPEN
    queue_manager = QueueManagerImpl(use_multiprocessing=False)
    kernel_manager = KernelManagerImpl(
        queue_manager=queue_manager,
        mode=SessionMode.RUN,
        configs={},
        app_metadata=app_metadata,
        config_manager=get_default_config_manager(current_path=None),
        virtual_file_storage="in_memory",
        redirect_console_to_browser=False,
    )

    await kernel_manager.start_kernel()

    # Instantiate a Session
    session = SessionImpl(
        session_view=SessionView(),
        initialization_id=session_id,
        session_consumer=session_consumer,
        kernel_manager=kernel_manager,
        app_file_manager=AppFileManager.from_app(InternalApp(App())),
        config_manager=get_default_config_manager(current_path=None),
        ttl_seconds=None,
        extensions=[],
    )

    # Assert startup
    assert session.room.main_consumer == session_consumer
    assert session._kernel_manager == kernel_manager
    session_consumer.on_attach.assert_called_once()
    assert session_consumer.on_detach.call_count == 0
    assert session.connection_state() == ConnectionState.OPEN

    # Create a kiosk consumer
    kiosk_consumer: Any = MagicMock()
    kiosk_consumer.connection_state.return_value = ConnectionState.OPEN
    session.connect_consumer(kiosk_consumer, main=False)

    # Assert startup of kiosk consumer
    assert session.room.main_consumer != kiosk_consumer
    assert kiosk_consumer.consumer_id in session.room.consumers
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
        workspace = SingleFileWorkspace.from_path(MarimoPath(tmp_file))
        session_manager = SessionManager(
            workspace=workspace,
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
        await session_manager.create_session(
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
        for _ in range(16):
            await asyncio.sleep(0.1)
            if len(session_consumer.notify_calls) > 0:
                break

        # Check that a document transaction was sent with the new code
        tx_ops = [
            op
            for op in session_consumer.notify_calls
            if isinstance(op, NotebookDocumentTransactionNotification)
        ]
        assert len(tx_ops) >= 1

        # Create another session for the same file
        session_consumer2 = MockSessionConsumer()
        await session_manager.create_session(
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
        for _ in range(16):
            await asyncio.sleep(0.1)
            if len(session_consumer.notify_calls) > 0:
                break

        # Both sessions should receive the update
        update_ops = [
            op
            for op in session_consumer.notify_calls
            if isinstance(op, NotebookDocumentTransactionNotification)
        ]
        update_ops2 = [
            op
            for op in session_consumer2.notify_calls
            if isinstance(op, NotebookDocumentTransactionNotification)
        ]
        assert len(update_ops) >= 1
        assert len(update_ops2) >= 1

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
        for _ in range(16):
            await asyncio.sleep(0.1)
            if len(session_consumer2.notify_calls) > 0:
                break

        # Only one session should receive the update
        update_ops2 = [
            op
            for op in session_consumer2.notify_calls
            if isinstance(op, NotebookDocumentTransactionNotification)
        ]
        assert len(update_ops2) >= 1
    finally:
        # Cleanup
        await session_manager.shutdown()


async def test_watch_mode_does_not_override_config(tmp_path: Path) -> None:
    """Test that watch mode does not override config settings."""
    # Create a temporary file
    tmp_file = tmp_path / "test_watch_mode_config_override.py"
    tmp_file.write_text("import marimo as mo")

    # Create a default config (autosave enabled by default)
    config_reader = get_default_config_manager(current_path=None)

    # Create a session manager with watch mode enabled
    workspace = SingleFileWorkspace.from_path(MarimoPath(str(tmp_file)))
    session_manager = SessionManager(
        workspace=workspace,
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
        workspace=workspace,
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
        await session_manager.shutdown()
        await session_manager_no_watch.shutdown()


@pytest.mark.flaky(reruns=3)
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
        workspace = SingleFileWorkspace.from_path(MarimoPath(str(tmp_file)))
        session_manager = SessionManager(
            workspace=workspace,
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
        session = await session_manager.create_session(
            session_id=session_id,
            session_consumer=session_consumer,
            query_params={},
            file_key=str(tmp_file),
            auto_instantiate=False,
        )
        mock_session_view = MagicMock(spec=SessionView)
        session.session_view = mock_session_view

        # Wait for file watcher to be initialized by checking it exists
        for _ in range(20):
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

        # Wait for the watcher to detect the change and send transaction
        tx_ops: list[NotebookDocumentTransactionNotification] = []
        for _ in range(20):
            await asyncio.sleep(0.1)
            tx_ops = [
                op
                for op in session_consumer.notify_calls
                if isinstance(op, NotebookDocumentTransactionNotification)
            ]
            if tx_ops:
                break

        # Check that a document transaction was sent (autorun)
        assert len(tx_ops) >= 1

        # Verify that cells were queued for execution
        assert session.session_view.add_control_request.called
        last_call = session.session_view.add_control_request.call_args[0][0]
        assert isinstance(last_call, SyncGraphCommand)

    finally:
        # Cleanup
        if session_manager:
            await session_manager.shutdown()


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
        workspace = SingleFileWorkspace.from_path(MarimoPath(str(tmp_file)))
        session_manager = SessionManager(
            workspace=workspace,
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
        session = await session_manager.create_session(
            session_id=session_id,
            session_consumer=session_consumer,
            query_params={},
            file_key=str(tmp_file),
            auto_instantiate=False,
        )

        # Wait a bit for session to be ready
        for _ in range(16):
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
        for _ in range(16):
            await asyncio.sleep(0.1)
            if len(session_consumer.notify_calls) > 0:
                break

        # Check that a document transaction was sent (lazy mode)
        tx_ops = [
            op
            for op in session_consumer.notify_calls
            if isinstance(op, NotebookDocumentTransactionNotification)
        ]
        assert len(tx_ops) >= 1

    finally:
        # Cleanup
        if session_manager:
            await session_manager.shutdown()


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
        workspace = SingleFileWorkspace.from_path(MarimoPath(str(tmp_path1)))
        session_manager = SessionManager(
            workspace=workspace,
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
        await session_manager.create_session(
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
        stable_id = session.stable_id
        success, error = await session_manager.rename_session(
            session_id, str(new_path)
        )
        assert success
        assert error is None
        assert new_path.exists()
        assert (
            session_manager.get_session_by_file_key(str(new_path)) is session
        )
        assert session.stable_id == stable_id

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
        for _ in range(16):
            await asyncio.sleep(0.1)
            if len(operations) > 0:
                break

        # Check that a document transaction was sent with the new code
        tx_ops = [
            op
            for op in operations
            if isinstance(op, NotebookDocumentTransactionNotification)
        ]
        assert len(tx_ops) >= 1

    finally:
        # Cleanup
        await session_manager.shutdown()
        if new_path.exists():
            os.remove(new_path)
        if tmp_path1.exists():  # noqa: ASYNC240
            os.remove(tmp_path1)


async def test_session_with_script_config_overrides(
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
    startup = SessionStartup()
    session = await SessionImpl.create(
        startup=startup,
        initialization_id="test_id",
        session_consumer=session_consumer,
        mode=SessionMode.RUN,
        app_metadata=app_metadata,
        app_file_manager=app_file_manager,
        config_manager=get_default_config_manager(current_path=None),
        virtual_file_storage="in_memory",
        redirect_console_to_browser=False,
        ttl_seconds=None,
        auto_instantiate=True,
    )

    assert session.session_view is startup.view

    # Verify that the session's config is affected by the script config
    assert (
        session.config_manager.get_config()["formatting"]["line_length"] == 999
    )
    assert (
        session._kernel_manager.config_manager.get_config()["formatting"][
            "line_length"
        ]
        == 999
    )

    # Cleanup
    session.close()


async def test_caching_extension_respects_mode_and_config() -> None:
    """Test caching enablement and mode across edit/run sessions."""
    from marimo._session.extensions.extensions import (
        CacheMode,
        CachingExtension,
    )

    session_consumer = MagicMock()
    session_consumer.connection_state.return_value = ConnectionState.OPEN

    async def create_session(
        mode: SessionMode,
        auto_instantiate: bool,
        *,
        serve_cached_sessions_in_apps: bool | None = None,
    ) -> Session:
        config_manager = get_default_config_manager(current_path=None)
        if serve_cached_sessions_in_apps is not None:
            config_manager = config_manager.with_overrides(
                {
                    "runtime": {
                        "serve_cached_sessions_in_apps": serve_cached_sessions_in_apps
                    }
                }
            )
        return await SessionImpl.create(
            startup=SessionStartup(),
            initialization_id="test_session",
            session_consumer=session_consumer,
            mode=mode,
            app_metadata=app_metadata,
            app_file_manager=AppFileManager.from_app(InternalApp(App())),
            config_manager=config_manager,
            virtual_file_storage="shared_memory"
            if mode == SessionMode.EDIT
            else "in_memory",
            redirect_console_to_browser=False,
            ttl_seconds=None,
            auto_instantiate=auto_instantiate,
        )

    def find_caching_extension(session: Session) -> CachingExtension:
        extension = [
            ext
            for ext in session.extensions
            if isinstance(ext, CachingExtension)
        ]
        assert len(extension) == 1
        return extension[0]

    # Test 1: EDIT mode with auto_instantiate=False -> caching enabled/read-write
    session_edit = await create_session(SessionMode.EDIT, False)

    # Find the CachingExtension
    caching_extension_edit = find_caching_extension(session_edit)
    assert caching_extension_edit.enabled is True
    assert caching_extension_edit.mode is CacheMode.READ_WRITE

    # Test 2: EDIT mode with auto_instantiate=True -> caching disabled
    session_edit_disabled = await create_session(SessionMode.EDIT, True)
    caching_extension_edit_disabled = find_caching_extension(
        session_edit_disabled
    )
    assert caching_extension_edit_disabled.enabled is False
    assert caching_extension_edit_disabled.mode is CacheMode.READ_WRITE

    # Test 3: RUN mode with config disabled -> caching disabled/read-only
    session_run_disabled = await create_session(
        SessionMode.RUN, True, serve_cached_sessions_in_apps=False
    )

    # Find the CachingExtension
    caching_extension_run_disabled = find_caching_extension(
        session_run_disabled
    )
    assert caching_extension_run_disabled.enabled is False
    assert caching_extension_run_disabled.mode is CacheMode.READ

    # Test 4: RUN mode with config enabled -> caching enabled/read-only
    session_run_enabled = await create_session(
        SessionMode.RUN, True, serve_cached_sessions_in_apps=True
    )
    caching_extension_run_enabled = find_caching_extension(session_run_enabled)
    assert caching_extension_run_enabled.enabled is True
    assert caching_extension_run_enabled.mode is CacheMode.READ

    # Cleanup
    session_edit.close()
    session_edit_disabled.close()
    session_run_disabled.close()
    session_run_enabled.close()
