# Copyright 2026 Marimo. All rights reserved.
"""Tests for session extensions."""

from __future__ import annotations

import asyncio
from unittest.mock import Mock, patch

import pytest

from marimo._messaging.notification import BannerNotification
from marimo._session.events import SessionEventBus
from marimo._session.extensions.extensions import (
    CacheMode,
    CachingExtension,
    HeartbeatExtension,
    LoggingExtension,
    NotificationListenerExtension,
    QueueExtension,
    ReplayExtension,
    SessionViewExtension,
)
from marimo._session.extensions.types import (
    EventAwareExtension,
    ExtensionRegistry,
)
from marimo._session.model import ConnectionState, SessionMode
from marimo._session.types import KernelExitInfo, KernelState
from marimo._types.ids import CellId_t, RequestId, SessionId


@pytest.fixture
def mock_session():
    """Create a mock session."""
    session = Mock()
    session.initialization_id = "test-session-id"
    session.kernel_state = Mock(return_value=KernelState.RUNNING)
    session.connection_state = Mock(return_value=ConnectionState.OPEN)
    session.close = Mock()
    session.ttl_seconds = 60
    session.session_view = Mock()

    # Mock app_file_manager
    session.app_file_manager = Mock()
    session.app_file_manager.filename = "test.py"
    session.app_file_manager.path = "/path/to/test.py"
    session.app_file_manager.app.cell_manager.cell_data = Mock(return_value=[])
    session.app_file_manager.app.cell_manager.cell_ids = Mock(return_value=[])

    return session


@pytest.fixture
def event_bus():
    """Create event bus for testing."""
    return SessionEventBus()


class TestHeartbeatExtension:
    """Tests for HeartbeatExtension."""

    async def test_lifecycle(self, mock_session, event_bus) -> None:
        """Test heartbeat start, stop, and cleanup on detach."""
        extension = HeartbeatExtension()
        extension.on_attach(mock_session, event_bus)

        assert extension.heartbeat_task is not None

        task = extension.heartbeat_task
        extension.on_detach()
        await asyncio.sleep(0.1)

        assert task.cancelled()

    async def test_detects_dead_kernel(self, mock_session, event_bus) -> None:
        """Test that heartbeat detects when kernel dies and closes session."""
        mock_session.kernel_state.return_value = KernelState.STOPPED
        mock_session.kernel_exit_info.return_value = KernelExitInfo(
            exitcode=-9,
            cause="oom",
            message=(
                "The kernel ran out of memory and was stopped. "
                "Notebook used 1952 MiB of the 2048 MiB limit. "
                "Click Restart to start a fresh kernel."
            ),
        )
        extension = HeartbeatExtension()
        extension.on_attach(mock_session, event_bus)

        await asyncio.sleep(1.5)

        mock_session.close.assert_called_once()
        # A persistent banner is broadcast before the session closes, so the
        # frontend can show the cause instead of just a "disconnected" toast.
        mock_session.notify.assert_called_once()
        banner = mock_session.notify.call_args.args[0]
        assert isinstance(banner, BannerNotification)
        assert banner.variant == "danger"
        assert banner.action == "restart"
        assert "out of memory" in banner.description
        assert "restart" in banner.description.lower()
        extension.on_detach()


class TestCachingExtension:
    """Tests for CachingExtension."""

    def test_disabled(self, mock_session, event_bus) -> None:
        """Test that disabled caching does nothing."""
        extension = CachingExtension(enabled=False)
        extension.on_attach(mock_session, event_bus)

        assert extension.session_cache_manager is None

    @patch("marimo._session.extensions.extensions.SessionCacheManager")
    def test_lifecycle(self, mock_cache_cls, mock_session, event_bus) -> None:
        """Test cache manager creation, start, and stop."""
        mock_cache = Mock()
        mock_cache_cls.return_value = mock_cache
        mock_cache.read_session_view = Mock(
            return_value=mock_session.session_view
        )

        extension = CachingExtension(enabled=True)
        extension.on_attach(mock_session, event_bus)

        mock_cache.start.assert_called_once()

        extension.on_detach()

        mock_cache.stop.assert_called_once()

    @patch("marimo._session.extensions.extensions.SessionCacheManager")
    def test_read_only_mode_skips_start(
        self, mock_cache_cls, mock_session, event_bus
    ) -> None:
        """Test that read-only mode does not start the cache writer."""
        mock_cache = Mock()
        mock_cache_cls.return_value = mock_cache
        mock_cache.read_session_view = Mock(
            return_value=mock_session.session_view
        )

        extension = CachingExtension(enabled=True, mode=CacheMode.READ)
        extension.on_attach(mock_session, event_bus)

        mock_cache.start.assert_not_called()
        mock_cache.read_session_view.assert_called_once()

        extension.on_detach()

    @patch("marimo._session.extensions.extensions.SessionCacheManager")
    async def test_rename_updates_path(
        self, mock_cache_cls, mock_session, event_bus
    ) -> None:
        """Test that renaming updates cache manager path."""
        mock_cache = Mock()
        mock_cache_cls.return_value = mock_cache
        mock_cache.read_session_view = Mock(
            return_value=mock_session.session_view
        )

        extension = CachingExtension(enabled=True)
        extension.on_attach(mock_session, event_bus)

        mock_session.app_file_manager.path = "/new/path.py"
        await extension.on_session_notebook_renamed(
            mock_session, "/old/path.py"
        )

        mock_cache.rename_path.assert_called_once_with("/new/path.py")
        extension.on_detach()

    @patch("marimo._session.extensions.extensions.SessionCacheManager")
    async def test_read_only_mode_ignores_rename(
        self, mock_cache_cls, mock_session, event_bus
    ) -> None:
        """Test that read-only mode ignores rename events."""
        mock_cache = Mock()
        mock_cache_cls.return_value = mock_cache
        mock_cache.read_session_view = Mock(
            return_value=mock_session.session_view
        )

        extension = CachingExtension(enabled=True, mode=CacheMode.READ)
        extension.on_attach(mock_session, event_bus)

        mock_session.app_file_manager.path = "/new/path.py"
        await extension.on_session_notebook_renamed(
            mock_session, "/old/path.py"
        )

        mock_cache.rename_path.assert_not_called()
        extension.on_detach()


class TestNotificationListenerExtension:
    """Tests for NotificationListenerExtension."""

    @pytest.fixture
    def kernel_manager(self):
        manager = Mock()
        manager.mode = SessionMode.EDIT
        manager.kernel_connection = Mock()
        manager.kernel_connection.fileno = Mock(return_value=1)
        return manager

    @pytest.fixture
    def queue_manager(self):
        manager = Mock()
        # For original edit mode, stream_queue is None
        manager.stream_queue = None
        return manager

    @pytest.fixture
    def queue_manager_with_stream(self):
        manager = Mock()
        # For run mode and IPC mode, stream_queue is set
        manager.stream_queue = asyncio.Queue()
        return manager

    @patch("marimo._session.extensions.extensions.ConnectionDistributor")
    def test_lifecycle(
        self, mock_dist, mock_session, event_bus, kernel_manager, queue_manager
    ) -> None:
        """Test distributor creation, start, and stop."""
        mock_distributor = Mock()
        mock_dist.return_value = mock_distributor

        extension = NotificationListenerExtension(
            kernel_manager, queue_manager
        )
        extension.on_attach(mock_session, event_bus)

        assert extension.distributor is not None
        mock_distributor.start.assert_called_once()

        extension.on_detach()

        mock_distributor.stop.assert_called_once()
        assert extension.distributor is None

    def test_uses_correct_distributor_type(
        self, kernel_manager, queue_manager, queue_manager_with_stream
    ) -> None:
        """Test that correct distributor type is used based on stream_queue."""
        from marimo._utils.distributor import (
            ConnectionDistributor,
            QueueDistributor,
        )

        # When stream_queue is None, use ConnectionDistributor (edit mode)
        extension = NotificationListenerExtension(
            kernel_manager, queue_manager
        )
        distributor = extension._create_distributor(
            kernel_manager, queue_manager
        )
        assert isinstance(distributor, ConnectionDistributor)

        # When stream_queue is present, use QueueDistributor (run mode or IPC)
        extension2 = NotificationListenerExtension(
            kernel_manager, queue_manager_with_stream
        )
        distributor = extension2._create_distributor(
            kernel_manager, queue_manager_with_stream
        )
        assert isinstance(distributor, QueueDistributor)


class TestLoggingExtension:
    """Tests for LoggingExtension."""

    def test_lifecycle(self, mock_session, event_bus) -> None:
        """Test event subscription and logging on attach/detach."""
        mock_logger = Mock()
        extension = LoggingExtension(logger=mock_logger)

        extension.on_attach(mock_session, event_bus)

        assert extension in event_bus._listeners
        mock_logger.debug.assert_called_with("Attaching extensions")

        extension.on_detach()

        assert extension not in event_bus._listeners
        assert mock_logger.debug.call_count >= 2

    async def test_session_events_logging(
        self, mock_session, event_bus
    ) -> None:
        """Test that session events are logged correctly."""
        mock_logger = Mock()
        extension = LoggingExtension(logger=mock_logger)
        extension.on_attach(mock_session, event_bus)

        # Test session created
        await extension.on_session_created(mock_session)
        mock_logger.debug.assert_any_call(
            "Session created: %s", mock_session.initialization_id
        )

        # Test session closed
        await extension.on_session_closed(mock_session)
        mock_logger.debug.assert_any_call(
            "Session closed: %s", mock_session.initialization_id
        )

        # Test session resumed
        await extension.on_session_resumed(mock_session, SessionId("old-id"))
        mock_logger.debug.assert_any_call(
            "Session resumed: %s (old id: %s)",
            mock_session.initialization_id,
            "old-id",
        )

        # Test notebook renamed
        await extension.on_session_notebook_renamed(
            mock_session, "/old/path.py"
        )
        mock_logger.debug.assert_any_call(
            "Session file renamed: %s (new path: %s)",
            mock_session.initialization_id,
            "/old/path.py",
        )

        extension.on_detach()


class TestSessionViewExtension:
    """Tests for SessionViewExtension."""

    def test_lifecycle(self, mock_session, event_bus) -> None:
        """Test event subscription on attach/detach."""
        extension = SessionViewExtension()

        extension.on_attach(mock_session, event_bus)

        assert extension in event_bus._listeners
        assert extension._event_bus is not None

        extension.on_detach()

        assert extension not in event_bus._listeners
        assert extension._event_bus is None

    def test_command_added_to_view(self, mock_session, event_bus) -> None:
        """Test that commands are added to session view."""
        from marimo._runtime.commands import ExecuteCellsCommand

        extension = SessionViewExtension()
        extension.on_attach(mock_session, event_bus)

        cmd = ExecuteCellsCommand(
            cell_ids=[CellId_t("cell1")], codes=["x = 1"]
        )
        extension.on_received_command(mock_session, cmd, None)

        mock_session.session_view.add_control_request.assert_called_once_with(
            cmd
        )
        extension.on_detach()

    def test_completion_not_added_to_view(
        self, mock_session, event_bus
    ) -> None:
        """Test that code completion commands are not added to view."""
        from marimo._runtime.commands import CodeCompletionCommand

        extension = SessionViewExtension()
        extension.on_attach(mock_session, event_bus)

        cmd = CodeCompletionCommand(
            id=RequestId("1"), document="", cell_id=CellId_t("cell1")
        )
        extension.on_received_command(mock_session, cmd, None)

        mock_session.session_view.add_control_request.assert_not_called()
        extension.on_detach()

    def test_stdin_added_to_view(self, mock_session, event_bus) -> None:
        """Test that stdin is added to session view."""
        extension = SessionViewExtension()
        extension.on_attach(mock_session, event_bus)

        extension.on_received_stdin(mock_session, "test input")

        mock_session.session_view.add_stdin.assert_called_once_with(
            "test input"
        )
        extension.on_detach()

    def test_notification_added_to_view(self, mock_session, event_bus) -> None:
        """Test that notifications are added to session view."""
        extension = SessionViewExtension()
        extension.on_attach(mock_session, event_bus)

        notification = Mock()
        extension.on_notification_sent(mock_session, notification)

        mock_session.session_view.add_raw_notification.assert_called_once_with(
            notification
        )
        extension.on_detach()


class TestQueueExtension:
    """Tests for QueueExtension."""

    @pytest.fixture
    def queue_manager(self):
        manager = Mock()
        manager.put_control_request = Mock()
        manager.put_input = Mock()
        return manager

    def test_lifecycle(self, mock_session, event_bus, queue_manager) -> None:
        """Test event subscription on attach/detach."""
        extension = QueueExtension(queue_manager)

        extension.on_attach(mock_session, event_bus)

        assert extension in event_bus._listeners
        assert extension._event_bus is not None

        extension.on_detach()

        assert extension not in event_bus._listeners
        assert extension._event_bus is None

    def test_command_added_to_queue(
        self, mock_session, event_bus, queue_manager
    ) -> None:
        """Test that commands are added to queue."""
        from marimo._runtime.commands import ExecuteCellsCommand

        extension = QueueExtension(queue_manager)
        extension.on_attach(mock_session, event_bus)

        cmd = ExecuteCellsCommand(
            cell_ids=[CellId_t("cell1")], codes=["x = 1"]
        )
        extension.on_received_command(mock_session, cmd, None)

        queue_manager.put_control_request.assert_called_once_with(cmd)
        extension.on_detach()

    def test_stdin_added_to_queue(
        self, mock_session, event_bus, queue_manager
    ) -> None:
        """Test that stdin is added to queue."""
        extension = QueueExtension(queue_manager)
        extension.on_attach(mock_session, event_bus)

        extension.on_received_stdin(mock_session, "test input")

        queue_manager.put_input.assert_called_once_with("test input")
        extension.on_detach()


class TestReplayExtension:
    """Tests for ReplayExtension."""

    def test_lifecycle(self, mock_session, event_bus) -> None:
        """Test event subscription on attach/detach."""
        extension = ReplayExtension()

        extension.on_attach(mock_session, event_bus)

        assert extension in event_bus._listeners
        assert extension._event_bus is not None

        extension.on_detach()

        assert extension not in event_bus._listeners
        assert extension._event_bus is None

    def test_execute_command_replayed(self, mock_session, event_bus) -> None:
        """Test that ExecuteCellsCommand is replayed with notifications."""
        from marimo._runtime.commands import ExecuteCellsCommand

        mock_session.notify = Mock()
        extension = ReplayExtension()
        extension.on_attach(mock_session, event_bus)

        cmd = ExecuteCellsCommand(
            cell_ids=[CellId_t("cell1")], codes=["x = 1"]
        )
        extension.on_received_command(mock_session, cmd, None)

        assert mock_session.notify.call_count == 1
        extension.on_detach()

    def test_sync_graph_command_replayed(
        self, mock_session, event_bus
    ) -> None:
        """Test that SyncGraphCommand is replayed with notifications."""
        from marimo._runtime.commands import SyncGraphCommand

        mock_session.notify = Mock()
        extension = ReplayExtension()
        extension.on_attach(mock_session, event_bus)

        cell_id = CellId_t("cell1")
        cmd = SyncGraphCommand(
            cells={cell_id: "x = 1"},
            run_ids=[cell_id],
            delete_ids=[],
        )
        extension.on_received_command(mock_session, cmd, None)

        assert mock_session.notify.call_count == 1
        extension.on_detach()

    def test_other_commands_not_replayed(
        self, mock_session, event_bus
    ) -> None:
        """Test that other commands are not replayed."""
        from marimo._runtime.commands import CodeCompletionCommand

        mock_session.notify = Mock()
        extension = ReplayExtension()
        extension.on_attach(mock_session, event_bus)

        cmd = CodeCompletionCommand(
            id=RequestId("1"), document="", cell_id=CellId_t("cell1")
        )
        extension.on_received_command(mock_session, cmd, None)

        mock_session.notify.assert_not_called()
        extension.on_detach()


class TestEventAwareExtension:
    """Tests for EventAwareExtension base class."""

    def test_attach_subscribes_and_sets_state(
        self, mock_session, event_bus
    ) -> None:
        ext = EventAwareExtension()
        ext.on_attach(mock_session, event_bus)

        assert ext._session is mock_session
        assert ext._event_bus is event_bus
        assert ext in event_bus._listeners
        # Properties work while attached
        assert ext.session is mock_session
        assert ext.event_bus is event_bus

    def test_detach_unsubscribes_and_clears_state(
        self, mock_session, event_bus
    ) -> None:
        ext = EventAwareExtension()
        ext.on_attach(mock_session, event_bus)
        ext.on_detach()

        assert ext._session is None
        assert ext._event_bus is None
        assert ext not in event_bus._listeners

    def test_properties_raise_when_detached(self) -> None:
        ext = EventAwareExtension()
        with pytest.raises(RuntimeError):
            ext.session  # noqa: B018
        with pytest.raises(RuntimeError):
            ext.event_bus  # noqa: B018

    def test_detach_without_attach_is_safe(self) -> None:
        ext = EventAwareExtension()
        ext.on_detach()  # should not raise


class TestNotificationListenerFlush:
    """Tests for NotificationListenerExtension.flush()."""

    def test_flush_delegates_to_distributor(self) -> None:
        ext = NotificationListenerExtension(Mock(), Mock())
        ext.distributor = Mock()
        ext.flush()
        ext.distributor.flush.assert_called_once()

    def test_flush_noop_without_distributor(self) -> None:
        ext = NotificationListenerExtension(Mock(), Mock())
        ext.distributor = None
        ext.flush()  # should not raise


class TestExtensionRegistry:
    """Tests for ExtensionRegistry."""

    def test_add_and_iterate(self) -> None:
        reg = ExtensionRegistry()
        a, b = Mock(), Mock()
        reg.add(a, b)
        assert list(reg) == [a, b]

    def test_remove(self) -> None:
        reg = ExtensionRegistry()
        a = Mock()
        reg.add(a)
        reg.remove(a)
        assert a not in reg

    def test_remove_missing_is_safe(self) -> None:
        reg = ExtensionRegistry()
        reg.remove(Mock())  # should not raise

    def test_get_by_type(self) -> None:
        reg = ExtensionRegistry()
        ext = LoggingExtension()
        reg.add(ext)
        assert reg.get(LoggingExtension) is ext
        assert reg.get(HeartbeatExtension) is None

    def test_iter_snapshots_list(self) -> None:
        """Iteration uses a snapshot so mutations during iteration are safe."""
        reg = ExtensionRegistry()
        a, b = Mock(), Mock()
        reg.add(a, b)
        items = iter(reg)  # snapshot taken here
        reg.remove(b)
        assert list(items) == [a, b]  # snapshot still has b
        assert b not in reg


class TestEventBusEmitSafety:
    """Tests that _emit snapshots the listener list."""

    def test_unsubscribe_during_emit_is_safe(self) -> None:
        bus = SessionEventBus()
        calls: list[str] = []

        listener_a = Mock()
        listener_b = Mock()

        listener_a.on_received_stdin = lambda _s, _t: (
            calls.append("a"),
            bus.unsubscribe(listener_a),
        )
        listener_b.on_received_stdin = lambda _s, _t: calls.append("b")

        bus.subscribe(listener_a)
        bus.subscribe(listener_b)
        bus.emit_received_stdin(Mock(), "hi")

        # Both were called even though a unsubscribed itself mid-emit
        assert calls == ["a", "b"]
        assert listener_a not in bus._listeners
