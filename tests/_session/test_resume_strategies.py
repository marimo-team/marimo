# Copyright 2026 Marimo. All rights reserved.
"""Tests for resume_strategies module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from marimo._server.exceptions import InvalidSessionException
from marimo._server.resume_strategies import (
    EditModeResumeStrategy,
    RunModeResumeStrategy,
)
from marimo._session.model import ConnectionState
from marimo._session.session_repository import SessionRepository
from marimo._types.ids import SessionId


def create_mock_session(
    file_path: str,
    connection_state: ConnectionState,
    initialization_id: str | None = None,
):
    """Create a mock session for testing."""
    session = MagicMock()
    session.app_file_manager = MagicMock()
    session.app_file_manager.path = os.path.abspath(file_path)
    session.initialization_id = initialization_id
    session.connection_state.return_value = connection_state
    return session


def test_edit_mode_resume_no_existing_sessions() -> None:
    """Test that edit mode returns None when no sessions exist."""
    repository = SessionRepository()
    strategy = EditModeResumeStrategy(repository, os.path.abspath)

    result = strategy.try_resume(SessionId("new-session"), "test.py")
    assert result is None


def test_edit_mode_resume_orphaned_session() -> None:
    """Test that edit mode resumes an orphaned session for the same file."""
    repository = SessionRepository()
    strategy = EditModeResumeStrategy(repository, os.path.abspath)

    # Create an orphaned session
    old_session_id = SessionId("old-session")
    orphaned_session = create_mock_session("test.py", ConnectionState.ORPHANED)
    repository.add_sync(old_session_id, orphaned_session)

    # Try to resume
    new_session_id = SessionId("new-session")
    result = strategy.try_resume(new_session_id, "test.py")

    # Should return the orphaned session
    assert result is orphaned_session

    # Session ID should be updated
    assert repository.get_sync(new_session_id) is orphaned_session
    assert repository.get_sync(old_session_id) is None


def test_edit_mode_resume_workspace_relative_key() -> None:
    """Regression: directory workspaces serve workspace-relative file keys.

    The key must be resolved through the workspace, not against the server
    CWD; sessions never resumed when the workspace root was a subdirectory
    of the CWD (`marimo edit notebooks/`).
    """
    repository = SessionRepository()
    # The notebook lives outside the CWD, like `marimo edit notebooks/`
    # run from a project root.
    resolved = os.path.abspath(
        os.path.join(os.sep, "workspace", "notebooks", "example.py")
    )
    strategy = EditModeResumeStrategy(
        repository,
        lambda key: resolved if key == "example.py" else None,
    )

    old_session_id = SessionId("old-session")
    session = create_mock_session(
        resolved, ConnectionState.ORPHANED, initialization_id="example.py"
    )
    repository.add_sync(old_session_id, session)

    new_session_id = SessionId("new-session")
    result = strategy.try_resume(new_session_id, "example.py")

    assert result is session
    assert repository.get_sync(new_session_id) is session


def test_edit_mode_resume_unresolvable_key_matches_initialization_id() -> None:
    """A key with no backing file (untitled or deleted notebook) still
    matches the session created under the same key."""
    repository = SessionRepository()
    strategy = EditModeResumeStrategy(repository, lambda _key: None)

    old_session_id = SessionId("old-session")
    session = create_mock_session(
        "test.py", ConnectionState.ORPHANED, initialization_id="__new__abc"
    )
    repository.add_sync(old_session_id, session)

    result = strategy.try_resume(SessionId("new-session"), "__new__abc")

    assert result is session


def test_edit_mode_resume_after_rename_matches_resolved_path() -> None:
    """A session keeps its creation key after a rename; the resolved path
    of the new key must still find it."""
    repository = SessionRepository()
    resolved = os.path.abspath(os.path.join(os.sep, "workspace", "renamed.py"))
    strategy = EditModeResumeStrategy(
        repository,
        lambda key: resolved if key == "renamed.py" else None,
    )

    session = create_mock_session(
        resolved, ConnectionState.ORPHANED, initialization_id="original.py"
    )
    repository.add_sync(SessionId("old-session"), session)

    result = strategy.try_resume(SessionId("new-session"), "renamed.py")

    assert result is session


def test_edit_mode_ignores_creation_key_when_file_resolves() -> None:
    """A recreated file must not match a session that moved away from it."""
    repository = SessionRepository()
    original = os.path.abspath(
        os.path.join(os.sep, "workspace", "original.py")
    )
    renamed = os.path.abspath(os.path.join(os.sep, "workspace", "renamed.py"))
    strategy = EditModeResumeStrategy(
        repository,
        lambda key: original if key == "original.py" else None,
    )

    session = create_mock_session(
        renamed, ConnectionState.ORPHANED, initialization_id="original.py"
    )
    old_session_id = SessionId("old-session")
    repository.add_sync(old_session_id, session)

    result = strategy.try_resume(SessionId("new-session"), "original.py")

    assert result is None
    assert repository.get_sync(old_session_id) is session


def test_edit_mode_reclaims_closed_session() -> None:
    """A CLOSED session (main consumer's socket closed but its disconnect
    not yet processed) is reclaimed like an orphaned one."""
    repository = SessionRepository()
    strategy = EditModeResumeStrategy(repository, os.path.abspath)

    old_session_id = SessionId("old-session")
    closed_session = create_mock_session("test.py", ConnectionState.CLOSED)
    repository.add_sync(old_session_id, closed_session)

    result = strategy.try_resume(SessionId("new-session"), "test.py")

    assert result is closed_session


def test_edit_mode_resume_open_session_not_resumed() -> None:
    """Test that edit mode doesn't resume a session with a live editor."""
    repository = SessionRepository()
    strategy = EditModeResumeStrategy(repository, os.path.abspath)

    # Create an open session
    old_session_id = SessionId("old-session")
    open_session = create_mock_session("test.py", ConnectionState.OPEN)
    repository.add_sync(old_session_id, open_session)

    # Try to resume
    new_session_id = SessionId("new-session")
    result = strategy.try_resume(new_session_id, "test.py")

    # Should return None because session has a live editor
    assert result is None

    # Original session should remain unchanged
    assert repository.get_sync(old_session_id) is open_session


def test_edit_mode_connecting_session_not_resumed() -> None:
    """A session mid-handshake must not be stolen by another connection."""
    repository = SessionRepository()
    strategy = EditModeResumeStrategy(repository, os.path.abspath)

    old_session_id = SessionId("old-session")
    connecting_session = create_mock_session(
        "test.py", ConnectionState.CONNECTING
    )
    repository.add_sync(old_session_id, connecting_session)

    result = strategy.try_resume(SessionId("new-session"), "test.py")

    assert result is None
    assert repository.get_sync(old_session_id) is connecting_session


def test_edit_mode_resume_different_file() -> None:
    """Test that edit mode doesn't resume session for different file."""
    repository = SessionRepository()
    strategy = EditModeResumeStrategy(repository, os.path.abspath)

    # Create an orphaned session for a different file
    old_session_id = SessionId("old-session")
    orphaned_session = create_mock_session(
        "other.py", ConnectionState.ORPHANED
    )
    repository.add_sync(old_session_id, orphaned_session)

    # Try to resume for different file
    new_session_id = SessionId("new-session")
    result = strategy.try_resume(new_session_id, "test.py")

    # Should return None because file doesn't match
    assert result is None


def test_edit_mode_resume_multiple_sessions_raises_error() -> None:
    """Test that edit mode raises error if multiple sessions exist for same file."""
    repository = SessionRepository()
    strategy = EditModeResumeStrategy(repository, os.path.abspath)

    # Create two sessions for the same file
    session1 = create_mock_session("test.py", ConnectionState.ORPHANED)
    session2 = create_mock_session("test.py", ConnectionState.ORPHANED)
    repository.add_sync(SessionId("session1"), session1)
    repository.add_sync(SessionId("session2"), session2)

    # Should raise exception
    with pytest.raises(
        InvalidSessionException,
        match="Only one session should exist while editing",
    ):
        strategy.try_resume(SessionId("new-session"), "test.py")


def test_run_mode_resume_no_existing_session() -> None:
    """Test that run mode returns None when session doesn't exist."""
    repository = SessionRepository()
    strategy = RunModeResumeStrategy(repository)

    result = strategy.try_resume(SessionId("non-existent"), "test.py")
    assert result is None


def test_run_mode_resume_orphaned_session() -> None:
    """Test that run mode resumes an orphaned session with matching ID."""
    repository = SessionRepository()
    strategy = RunModeResumeStrategy(repository)

    # Create an orphaned session
    session_id = SessionId("session-123")
    orphaned_session = create_mock_session("test.py", ConnectionState.ORPHANED)
    repository.add_sync(session_id, orphaned_session)

    # Try to resume with same ID
    result = strategy.try_resume(session_id, "test.py")

    # Should return the orphaned session
    assert result is orphaned_session


def test_run_mode_resume_open_session_not_resumed() -> None:
    """Test that run mode doesn't resume a non-orphaned session."""
    repository = SessionRepository()
    strategy = RunModeResumeStrategy(repository)

    # Create an open session
    session_id = SessionId("session-123")
    open_session = create_mock_session("test.py", ConnectionState.OPEN)
    repository.add_sync(session_id, open_session)

    # Try to resume
    result = strategy.try_resume(session_id, "test.py")

    # Should return None because session is not orphaned
    assert result is None


def test_run_mode_allows_multiple_sessions_same_file() -> None:
    """Test that run mode allows multiple sessions for the same file."""
    repository = SessionRepository()
    strategy = RunModeResumeStrategy(repository)

    # Create multiple orphaned sessions for the same file
    session1_id = SessionId("session-1")
    session2_id = SessionId("session-2")
    session1 = create_mock_session("test.py", ConnectionState.ORPHANED)
    session2 = create_mock_session("test.py", ConnectionState.ORPHANED)
    repository.add_sync(session1_id, session1)
    repository.add_sync(session2_id, session2)

    # Should be able to resume each by their ID
    result1 = strategy.try_resume(session1_id, "test.py")
    result2 = strategy.try_resume(session2_id, "test.py")

    assert result1 is session1
    assert result2 is session2
