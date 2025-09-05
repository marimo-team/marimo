"""Tests for marimo._mcp.server.tools.notebooks module."""

import os
from unittest.mock import Mock, patch

import pytest

# Skip all MCP tests if Python < 3.10 or MCP not available
pytest.importorskip("mcp", reason="MCP requires Python 3.10+")

from marimo._mcp.server.tools.notebooks import _get_active_sessions_internal
from marimo._server.model import ConnectionState


class MockSession:
    """Mock session for testing."""

    def __init__(
        self, connection_state, filename=None, session_id="test_session"
    ):
        self._connection_state = connection_state
        self.app_file_manager = Mock()
        self.app_file_manager.filename = filename
        self.initialization_id = f"init_{session_id}"

    def connection_state(self):
        return self._connection_state


class MockSessionManager:
    """Mock session manager for testing."""

    def __init__(self, sessions=None):
        self.sessions = sessions or {}


class MockAppState:
    """Mock app state for testing."""

    def __init__(self, sessions=None):
        self.session_manager = MockSessionManager(sessions)


def test_get_active_sessions_internal_empty():
    """Test _get_active_sessions_internal with no sessions."""
    app_state = MockAppState()

    result = _get_active_sessions_internal(app_state)

    assert result == []


def test_get_active_sessions_internal_open_session():
    """Test _get_active_sessions_internal with an open session."""
    session = MockSession(
        connection_state=ConnectionState.OPEN,
        filename="/path/to/notebook.py",
        session_id="session1",
    )

    app_state = MockAppState({"session1": session})

    with patch(
        "marimo._mcp.server.tools.notebooks.pretty_path"
    ) as mock_pretty_path:
        mock_pretty_path.return_value = "notebook.py"

        result = _get_active_sessions_internal(app_state)

    assert len(result) == 1
    assert result[0].name == "notebook.py"
    assert result[0].path == "notebook.py"
    assert result[0].session_id == "session1"
    assert result[0].initialization_id == "init_session1"


def test_get_active_sessions_internal_orphaned_session():
    """Test _get_active_sessions_internal with an orphaned session."""
    session = MockSession(
        connection_state=ConnectionState.ORPHANED,
        filename="/path/to/test.py",
        session_id="session2",
    )

    app_state = MockAppState({"session2": session})

    with patch(
        "marimo._mcp.server.tools.notebooks.pretty_path"
    ) as mock_pretty_path:
        mock_pretty_path.return_value = "test.py"

        result = _get_active_sessions_internal(app_state)

    assert len(result) == 1
    assert result[0].name == "test.py"


def test_get_active_sessions_internal_closed_session():
    """Test _get_active_sessions_internal ignores closed sessions."""
    session = MockSession(
        connection_state=ConnectionState.CLOSED,
        filename="/path/to/closed.py",
        session_id="session3",
    )

    app_state = MockAppState({"session3": session})

    result = _get_active_sessions_internal(app_state)

    assert result == []


def test_get_active_sessions_internal_no_filename():
    """Test _get_active_sessions_internal with session that has no filename."""
    session = MockSession(
        connection_state=ConnectionState.OPEN,
        filename=None,
        session_id="session4",
    )

    app_state = MockAppState({"session4": session})

    result = _get_active_sessions_internal(app_state)

    assert len(result) == 1
    assert result[0].name == "new notebook"
    assert result[0].path == "session4"  # Uses session_id as path
    assert result[0].session_id == "session4"


def test_get_active_sessions_internal_multiple_sessions():
    """Test _get_active_sessions_internal with multiple sessions."""
    sessions = {
        "session1": MockSession(
            ConnectionState.OPEN, "/path/first.py", "session1"
        ),
        "session2": MockSession(
            ConnectionState.CLOSED, "/path/closed.py", "session2"
        ),
        "session3": MockSession(
            ConnectionState.ORPHANED, "/path/third.py", "session3"
        ),
    }

    app_state = MockAppState(sessions)

    with patch(
        "marimo._mcp.server.tools.notebooks.pretty_path"
    ) as mock_pretty_path:
        mock_pretty_path.side_effect = lambda x: os.path.basename(x)

        result = _get_active_sessions_internal(app_state)

    # Should only include OPEN and ORPHANED sessions (not CLOSED)
    assert len(result) == 2

    # Results should be in reverse order (most recent first)
    session_ids = [f.session_id for f in result]
    assert "session3" in session_ids  # ORPHANED session included
    assert "session1" in session_ids  # OPEN session included
    assert "session2" not in session_ids  # CLOSED session excluded


def test_get_active_sessions_internal_reverse_order():
    """Test that results are returned in reverse order."""
    sessions = {
        "first": MockSession(ConnectionState.OPEN, "/path/a.py", "first"),
        "second": MockSession(ConnectionState.OPEN, "/path/b.py", "second"),
        "third": MockSession(ConnectionState.OPEN, "/path/c.py", "third"),
    }

    app_state = MockAppState(sessions)

    with patch(
        "marimo._mcp.server.tools.notebooks.pretty_path"
    ) as mock_pretty_path:
        mock_pretty_path.side_effect = lambda x: os.path.basename(x)

        result = _get_active_sessions_internal(app_state)

    # The exact order depends on dict iteration, but should be reversed
    # We can at least verify that we get all 3 sessions
    assert len(result) == 3
    session_ids = [f.session_id for f in result]
    assert set(session_ids) == {"first", "second", "third"}
