# Copyright 2026 Marimo. All rights reserved.
"""Tests for file_watcher_integration module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from marimo._session.events import SessionEventBus
from marimo._session.file_watcher_integration import (
    SessionFileWatcherExtension,
)
from marimo._session.session_repository import SessionRepository
from marimo._types.ids import SessionId
from marimo._utils.file_watcher import FileWatcherManager


def create_mock_session(file_path: str | None, css_file: str | None = None):
    """Create a mock session for testing."""
    session = MagicMock()
    session.app_file_manager = MagicMock()
    session.app_file_manager.path = file_path
    session.app_file_manager.app.config.css_file = css_file
    session.app_file_manager.read_css_file.return_value = (
        "body { color: red; }" if css_file else None
    )
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
        Path("/path/to/file.py").absolute(), callback
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
    # Detach without attaching first
    lifecycle.on_detach()

    watcher_manager.remove_callback.assert_not_called()


async def test_update_session_path(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
) -> None:
    """Test updating a session's file path."""
    session = create_mock_session("/path/to/old.py")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session, event_bus)

    # Attach to old path
    old_callback = watcher_manager.add_callback.call_args[0][1]

    # Update path
    session.app_file_manager.path = "/path/to/new.py"
    await lifecycle.on_session_notebook_renamed(session, "/path/to/old.py")

    # Verify old watcher was removed
    watcher_manager.remove_callback.assert_called_once_with(
        Path("/path/to/old.py").absolute(),  # noqa: ASYNC240
        old_callback,
    )

    # Verify new watcher was added
    assert watcher_manager.add_callback.call_count == 2
    new_call = watcher_manager.add_callback.call_args_list[1]
    assert new_call[0][0] == Path("/path/to/new.py").absolute()  # noqa: ASYNC240


async def test_file_change_callback_invoked(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
    file_change_callback: AsyncMock,
) -> None:
    """Test that file change callback is invoked correctly."""
    session = create_mock_session("/path/to/file.py")
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


async def test_listener_on_session_created_enabled(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
) -> None:
    """Test listener attaches watcher when session is created (enabled)."""

    session = create_mock_session("/path/to/file.py")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session, event_bus)

    # Verify watcher was attached
    watcher_manager.add_callback.assert_called_once()


async def test_listener_on_session_closed_disabled(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
) -> None:
    """Test listener does not detach watcher when disabled."""

    session = create_mock_session("/path/to/file.py")
    event_bus = SessionEventBus()
    lifecycle.on_attach(session, event_bus)

    # Verify watcher was not detached
    watcher_manager.remove_callback.assert_not_called()


def test_attach_with_css_file(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
    tmp_path: Path,
) -> None:
    """Test that CSS file watcher is registered when css_file is configured."""
    css_path = tmp_path / "custom.css"
    css_path.write_text("body { color: red; }")
    notebook_path = str(tmp_path / "notebook.py")

    session = create_mock_session(notebook_path, css_file="custom.css")
    lifecycle.on_attach(session, SessionEventBus())

    # Should register both notebook and CSS watchers
    assert watcher_manager.add_callback.call_count == 2
    css_call = watcher_manager.add_callback.call_args_list[1]
    assert css_call[0][0] == css_path


def test_attach_without_css_file(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
) -> None:
    """Test that no CSS watcher is registered when css_file is not set."""
    session = create_mock_session("/path/to/notebook.py")
    lifecycle.on_attach(session, SessionEventBus())

    # Should only register the notebook watcher
    assert watcher_manager.add_callback.call_count == 1


def test_attach_css_file_does_not_exist(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
    tmp_path: Path,
) -> None:
    """Test that no CSS watcher is registered when css_file doesn't exist."""
    notebook_path = str(tmp_path / "notebook.py")
    session = create_mock_session(notebook_path, css_file="missing.css")
    lifecycle.on_attach(session, SessionEventBus())

    # Should only register the notebook watcher
    assert watcher_manager.add_callback.call_count == 1


def test_detach_removes_css_watcher(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
    tmp_path: Path,
) -> None:
    """Test that CSS watcher is cleaned up on detach."""
    css_path = tmp_path / "custom.css"
    css_path.write_text("body { color: red; }")
    notebook_path = str(tmp_path / "notebook.py")

    session = create_mock_session(notebook_path, css_file="custom.css")
    lifecycle.on_attach(session, SessionEventBus())
    lifecycle.on_detach()

    # Should remove both notebook and CSS watchers
    assert watcher_manager.remove_callback.call_count == 2


async def test_css_change_sends_notification(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
    tmp_path: Path,
) -> None:
    """Test that CSS file change sends UpdateCssNotification."""
    from marimo._messaging.notification import UpdateCssNotification

    css_path = tmp_path / "custom.css"
    css_path.write_text("body { color: red; }")
    notebook_path = str(tmp_path / "notebook.py")

    session = create_mock_session(notebook_path, css_file="custom.css")
    lifecycle.on_attach(session, SessionEventBus())

    # Get the CSS callback (second add_callback call)
    css_callback = watcher_manager.add_callback.call_args_list[1][0][1]

    # Simulate CSS file change
    await css_callback(css_path)

    # Verify notification was sent
    session.notify.assert_called_once()
    notification = session.notify.call_args[0][0]
    assert isinstance(notification, UpdateCssNotification)
    assert notification.css == "body { color: red; }"


def test_update_css_watcher_add(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
    tmp_path: Path,
) -> None:
    """Test adding a CSS watcher mid-session."""
    notebook_path = str(tmp_path / "notebook.py")
    session = create_mock_session(notebook_path)
    lifecycle.on_attach(session, SessionEventBus())

    # Initially no CSS watcher
    assert watcher_manager.add_callback.call_count == 1

    # Now user sets css_file
    css_path = tmp_path / "custom.css"
    css_path.write_text("body { color: blue; }")
    session.app_file_manager.app.config.css_file = "custom.css"

    lifecycle.update_css_watcher(session)

    # Should have registered the new CSS watcher
    assert watcher_manager.add_callback.call_count == 2
    css_call = watcher_manager.add_callback.call_args_list[1]
    assert css_call[0][0] == css_path


def test_update_css_watcher_remove(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
    tmp_path: Path,
) -> None:
    """Test removing a CSS watcher mid-session."""
    css_path = tmp_path / "custom.css"
    css_path.write_text("body { color: red; }")
    notebook_path = str(tmp_path / "notebook.py")

    session = create_mock_session(notebook_path, css_file="custom.css")
    lifecycle.on_attach(session, SessionEventBus())

    # Now user clears css_file
    session.app_file_manager.app.config.css_file = None

    lifecycle.update_css_watcher(session)

    # Should have removed the old CSS watcher
    assert watcher_manager.remove_callback.call_count == 1


def test_update_css_watcher_change(
    lifecycle: SessionFileWatcherExtension,
    watcher_manager: MagicMock,
    tmp_path: Path,
) -> None:
    """Test changing from one CSS file to another mid-session."""
    old_css = tmp_path / "old.css"
    old_css.write_text("body { color: red; }")
    new_css = tmp_path / "new.css"
    new_css.write_text("body { color: blue; }")
    notebook_path = str(tmp_path / "notebook.py")

    session = create_mock_session(notebook_path, css_file="old.css")
    lifecycle.on_attach(session, SessionEventBus())

    # Change to new CSS file
    session.app_file_manager.app.config.css_file = "new.css"
    lifecycle.update_css_watcher(session)

    # Should remove old and add new
    assert watcher_manager.remove_callback.call_count == 1
    # 2 from attach (notebook + old CSS) + 1 from update (new CSS)
    assert watcher_manager.add_callback.call_count == 3
