# Copyright 2024 Marimo. All rights reserved.
"""Tests for file_watcher_integration module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from marimo._server.sessions.events import SessionEventBus
from marimo._server.sessions.file_watcher_integration import (
    SessionFileWatcherExtension,
)
from marimo._server.sessions.session_repository import SessionRepository
from marimo._types.ids import SessionId
from marimo._utils.file_watcher import FileWatcherManager


def create_mock_session(file_path: str | None):
    """Create a mock session for testing."""
    session = MagicMock()
    session.app_file_manager = MagicMock()
    session.app_file_manager.path = file_path
    return session


@pytest.fixture
def watcher_manager():
    """Create a mock file watcher manager."""
    return MagicMock(spec=FileWatcherManager)


@pytest.fixture
def repository():
    """Create a session repository."""
    return SessionRepository()


@pytest.fixture
def file_change_callback():
    """Create a mock file change callback."""
    return AsyncMock()


@pytest.fixture
def lifecycle(watcher_manager, file_change_callback):
    """Create a SessionFileWatcherLifecycle instance."""
    return SessionFileWatcherExtension(watcher_manager, file_change_callback)


def test_attach_session_with_path(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
) -> None:
    """Test attaching a file watcher to a session with a file path."""
    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session, SessionEventBus())

    # Verify watcher was added
    assert watcher_manager.add_callback.call_count == 1
    call_args = watcher_manager.add_callback.call_args
    assert call_args[0][0] == Path("/path/to/file.py")
    # Second arg is the callback function
    assert callable(call_args[0][1])


def test_attach_session_without_path(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
) -> None:
    """Test attaching a file watcher to a session without a file path."""
    session = create_mock_session(None)
    session_id = SessionId("test-session")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session, event_bus)

    # Verify watcher was not added
    watcher_manager.add_callback.assert_not_called()


def test_detach_session_with_path(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
) -> None:
    """Test detaching a file watcher from a session with a file path."""
    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session, event_bus)

    callback = watcher_manager.add_callback.call_args[0][1]

    # Then detach
    lifecycle.on_detach()

    # Verify watcher was removed with the same callback
    watcher_manager.remove_callback.assert_called_once_with(
        Path("/path/to/file.py"), callback
    )


def test_detach_session_without_path(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
) -> None:
    """Test detaching a file watcher from a session without a file path."""
    session = create_mock_session(None)
    session_id = SessionId("test-session")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session, event_bus)

    lifecycle.on_detach()

    # Verify watcher was not removed
    watcher_manager.remove_callback.assert_not_called()


def test_detach_session_not_attached(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
) -> None:
    """Test detaching a file watcher from a session that was never attached."""
    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session, event_bus)

    # Detach without attaching first
    lifecycle.on_detach()

    # Should not crash, just skip removal
    watcher_manager.remove_callback.assert_not_called()


def test_update_session_path(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
) -> None:
    """Test updating a session's file path."""
    session = create_mock_session("/path/to/old.py")
    session_id = SessionId("test-session")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session, event_bus)

    # Attach to old path
    old_callback = watcher_manager.add_callback.call_args[0][1]

    # Update path
    session.app_file_manager.path = "/path/to/new.py"
    lifecycle.on_session_notebook_renamed(session, Path("/path/to/old.py"))

    # Verify old watcher was removed
    watcher_manager.remove_callback.assert_called_once_with(
        Path("/path/to/old.py"), old_callback
    )

    # Verify new watcher was added
    assert watcher_manager.add_callback.call_count == 2
    new_call = watcher_manager.add_callback.call_args_list[1]
    assert new_call[0][0] == Path("/path/to/new.py")


def test_stop_all(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
) -> None:
    """Test stopping all file watchers."""
    # Attach multiple sessions
    session1 = create_mock_session("/path/to/file1.py")
    session2 = create_mock_session("/path/to/file2.py")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session1, event_bus)
    lifecycle.on_attach(session2, event_bus)

    # Stop all
    lifecycle.on_detach()

    # Verify watcher manager was stopped
    watcher_manager.stop_all.assert_called_once()


async def test_file_change_callback_invoked(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
    file_change_callback: AsyncMock,
) -> None:
    """Test that file change callback is invoked correctly."""
    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session, event_bus)

    # Attach session

    # Get the callback that was registered with the watcher
    registered_callback = watcher_manager.add_callback.call_args[0][1]

    # Simulate file change by calling the callback
    await registered_callback(Path("/path/to/file.py"))

    # Verify our file change callback was invoked
    file_change_callback.assert_called_once_with(
        Path("/path/to/file.py"), session
    )


async def test_file_change_callback_wrong_path_skipped(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
    file_change_callback: AsyncMock,
) -> None:
    """Test that file change callback is skipped for wrong path."""
    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session, event_bus)

    # Attach session

    # Get the callback that was registered with the watcher
    registered_callback = watcher_manager.add_callback.call_args[0][1]

    # Simulate file change with different path
    await registered_callback(Path("/path/to/different.py"))

    # Verify our file change callback was not invoked
    file_change_callback.assert_not_called()


async def test_listener_on_session_created_enabled(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
) -> None:
    """Test listener attaches watcher when session is created (enabled)."""

    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session, event_bus)

    # Verify watcher was attached
    watcher_manager.add_callback.assert_called_once()


async def test_listener_on_session_created_disabled(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
) -> None:
    """Test listener does not attach watcher when disabled."""

    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session, event_bus)

    # Verify watcher was not attached
    watcher_manager.add_callback.assert_not_called()


async def test_listener_on_session_closed_enabled(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
) -> None:
    """Test listener detaches watcher when session is closed (enabled)."""

    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session, event_bus)

    # First attach
    callback = watcher_manager.add_callback.call_args[0][1]

    # Then close

    # Verify watcher was detached
    watcher_manager.remove_callback.assert_called_once_with(
        Path("/path/to/file.py"), callback
    )


async def test_listener_on_session_closed_disabled(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
) -> None:
    """Test listener does not detach watcher when disabled."""

    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session, event_bus)

    # Verify watcher was not detached
    watcher_manager.remove_callback.assert_not_called()
