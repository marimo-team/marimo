# Copyright 2024 Marimo. All rights reserved.
"""Tests for file_watcher_integration module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from marimo._server.sessions.file_watcher_integration import (
    FileWatcherAttachmentListener,
    SessionFileWatcherLifecycle,
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
def lifecycle(watcher_manager, file_change_callback, repository):
    """Create a SessionFileWatcherLifecycle instance."""
    return SessionFileWatcherLifecycle(
        watcher_manager, file_change_callback, repository
    )


def test_attach_session_with_path(
    lifecycle: SessionFileWatcherLifecycle,
    watcher_manager: MagicMock,
    repository: SessionRepository,
) -> None:
    """Test attaching a file watcher to a session with a file path."""
    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    repository.add_sync(session_id, session)

    lifecycle.attach(session)

    # Verify watcher was added
    assert watcher_manager.add_callback.call_count == 1
    call_args = watcher_manager.add_callback.call_args
    assert call_args[0][0] == Path("/path/to/file.py")
    # Second arg is the callback function
    assert callable(call_args[0][1])


def test_attach_session_without_path(
    lifecycle: SessionFileWatcherLifecycle,
    watcher_manager: MagicMock,
    repository: SessionRepository,
) -> None:
    """Test attaching a file watcher to a session without a file path."""
    session = create_mock_session(None)
    session_id = SessionId("test-session")
    repository.add_sync(session_id, session)

    lifecycle.attach(session)

    # Verify watcher was not added
    watcher_manager.add_callback.assert_not_called()


def test_detach_session_with_path(
    lifecycle: SessionFileWatcherLifecycle,
    watcher_manager: MagicMock,
    repository: SessionRepository,
) -> None:
    """Test detaching a file watcher from a session with a file path."""
    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    repository.add_sync(session_id, session)

    # First attach
    lifecycle.attach(session)
    callback = watcher_manager.add_callback.call_args[0][1]

    # Then detach
    lifecycle.detach(session)

    # Verify watcher was removed with the same callback
    watcher_manager.remove_callback.assert_called_once_with(
        Path("/path/to/file.py"), callback
    )


def test_detach_session_without_path(
    lifecycle: SessionFileWatcherLifecycle,
    watcher_manager: MagicMock,
    repository: SessionRepository,
) -> None:
    """Test detaching a file watcher from a session without a file path."""
    session = create_mock_session(None)
    session_id = SessionId("test-session")
    repository.add_sync(session_id, session)

    lifecycle.detach(session)

    # Verify watcher was not removed
    watcher_manager.remove_callback.assert_not_called()


def test_detach_session_not_attached(
    lifecycle: SessionFileWatcherLifecycle,
    watcher_manager: MagicMock,
    repository: SessionRepository,
) -> None:
    """Test detaching a file watcher from a session that was never attached."""
    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    repository.add_sync(session_id, session)

    # Detach without attaching first
    lifecycle.detach(session)

    # Should not crash, just skip removal
    watcher_manager.remove_callback.assert_not_called()


def test_update_session_path(
    lifecycle: SessionFileWatcherLifecycle,
    watcher_manager: MagicMock,
    repository: SessionRepository,
) -> None:
    """Test updating a session's file path."""
    session = create_mock_session("/path/to/old.py")
    session_id = SessionId("test-session")
    repository.add_sync(session_id, session)

    # Attach to old path
    lifecycle.attach(session)
    old_callback = watcher_manager.add_callback.call_args[0][1]

    # Update path
    session.app_file_manager.path = "/path/to/new.py"
    lifecycle.update(session, Path("/path/to/old.py"), Path("/path/to/new.py"))

    # Verify old watcher was removed
    watcher_manager.remove_callback.assert_called_once_with(
        Path("/path/to/old.py"), old_callback
    )

    # Verify new watcher was added
    assert watcher_manager.add_callback.call_count == 2
    new_call = watcher_manager.add_callback.call_args_list[1]
    assert new_call[0][0] == Path("/path/to/new.py")


def test_stop_all(
    lifecycle: SessionFileWatcherLifecycle,
    watcher_manager: MagicMock,
    repository: SessionRepository,
) -> None:
    """Test stopping all file watchers."""
    # Attach multiple sessions
    session1 = create_mock_session("/path/to/file1.py")
    session2 = create_mock_session("/path/to/file2.py")
    repository.add_sync(SessionId("session1"), session1)
    repository.add_sync(SessionId("session2"), session2)

    lifecycle.attach(session1)
    lifecycle.attach(session2)

    # Stop all
    lifecycle.stop_all()

    # Verify watcher manager was stopped
    watcher_manager.stop_all.assert_called_once()


async def test_file_change_callback_invoked(
    lifecycle: SessionFileWatcherLifecycle,
    watcher_manager: MagicMock,
    file_change_callback: AsyncMock,
    repository: SessionRepository,
) -> None:
    """Test that file change callback is invoked correctly."""
    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    repository.add_sync(session_id, session)

    # Attach session
    lifecycle.attach(session)

    # Get the callback that was registered with the watcher
    registered_callback = watcher_manager.add_callback.call_args[0][1]

    # Simulate file change by calling the callback
    await registered_callback(Path("/path/to/file.py"))

    # Verify our file change callback was invoked
    file_change_callback.assert_called_once_with(
        Path("/path/to/file.py"), session
    )


async def test_file_change_callback_wrong_path_skipped(
    lifecycle: SessionFileWatcherLifecycle,
    watcher_manager: MagicMock,
    file_change_callback: AsyncMock,
    repository: SessionRepository,
) -> None:
    """Test that file change callback is skipped for wrong path."""
    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    repository.add_sync(session_id, session)

    # Attach session
    lifecycle.attach(session)

    # Get the callback that was registered with the watcher
    registered_callback = watcher_manager.add_callback.call_args[0][1]

    # Simulate file change with different path
    await registered_callback(Path("/path/to/different.py"))

    # Verify our file change callback was not invoked
    file_change_callback.assert_not_called()


async def test_listener_on_session_created_enabled(
    lifecycle: SessionFileWatcherLifecycle,
    watcher_manager: MagicMock,
    repository: SessionRepository,
) -> None:
    """Test listener attaches watcher when session is created (enabled)."""
    listener = FileWatcherAttachmentListener(lifecycle, enabled=True)

    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    repository.add_sync(session_id, session)

    await listener.on_session_created(session)

    # Verify watcher was attached
    watcher_manager.add_callback.assert_called_once()


async def test_listener_on_session_created_disabled(
    lifecycle: SessionFileWatcherLifecycle,
    watcher_manager: MagicMock,
    repository: SessionRepository,
) -> None:
    """Test listener does not attach watcher when disabled."""
    listener = FileWatcherAttachmentListener(lifecycle, enabled=False)

    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    repository.add_sync(session_id, session)

    await listener.on_session_created(session)

    # Verify watcher was not attached
    watcher_manager.add_callback.assert_not_called()


async def test_listener_on_session_closed_enabled(
    lifecycle: SessionFileWatcherLifecycle,
    watcher_manager: MagicMock,
    repository: SessionRepository,
) -> None:
    """Test listener detaches watcher when session is closed (enabled)."""
    listener = FileWatcherAttachmentListener(lifecycle, enabled=True)

    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    repository.add_sync(session_id, session)

    # First attach
    await listener.on_session_created(session)
    callback = watcher_manager.add_callback.call_args[0][1]

    # Then close
    await listener.on_session_closed(session)

    # Verify watcher was detached
    watcher_manager.remove_callback.assert_called_once_with(
        Path("/path/to/file.py"), callback
    )


async def test_listener_on_session_closed_disabled(
    lifecycle: SessionFileWatcherLifecycle,
    watcher_manager: MagicMock,
    repository: SessionRepository,
) -> None:
    """Test listener does not detach watcher when disabled."""
    listener = FileWatcherAttachmentListener(lifecycle, enabled=False)

    session = create_mock_session("/path/to/file.py")
    session_id = SessionId("test-session")
    repository.add_sync(session_id, session)

    await listener.on_session_closed(session)

    # Verify watcher was not detached
    watcher_manager.remove_callback.assert_not_called()
