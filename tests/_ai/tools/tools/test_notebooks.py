from __future__ import annotations

import os
from unittest.mock import Mock, patch

from marimo._ai.tools.tools.notebooks import GetActiveNotebooks
from marimo._server.model import ConnectionState


class MockSession:
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
    def __init__(self, sessions=None):
        self.sessions = sessions or {}


class MockAppState:
    def __init__(self, sessions=None):
        self.session_manager = MockSessionManager(sessions)


def test_get_active_sessions_internal_empty():
    tool = GetActiveNotebooks(app=None)
    result = tool._get_active_sessions_internal(MockAppState())
    assert result == []


def test_get_active_sessions_internal_open_session():
    tool = GetActiveNotebooks(app=None)
    session = MockSession(
        connection_state=ConnectionState.OPEN,
        filename="/path/to/notebook.py",
        session_id="session1",
    )
    app_state = MockAppState({"session1": session})

    with patch(
        "marimo._ai.tools.tools.notebooks.pretty_path"
    ) as mock_pretty_path:
        mock_pretty_path.return_value = "notebook.py"
        result = tool._get_active_sessions_internal(app_state)

    assert len(result) == 1
    assert result[0].name == "notebook.py"
    assert result[0].path == "notebook.py"
    assert result[0].session_id == "session1"
    assert result[0].initialization_id == "init_session1"


def test_get_active_sessions_internal_orphaned_session():
    tool = GetActiveNotebooks(app=None)
    session = MockSession(
        connection_state=ConnectionState.ORPHANED,
        filename="/path/to/test.py",
        session_id="session2",
    )
    app_state = MockAppState({"session2": session})

    with patch(
        "marimo._ai.tools.tools.notebooks.pretty_path"
    ) as mock_pretty_path:
        mock_pretty_path.return_value = "test.py"
        result = tool._get_active_sessions_internal(app_state)

    assert len(result) == 1
    assert result[0].name == "test.py"


def test_get_active_sessions_internal_closed_session():
    tool = GetActiveNotebooks(app=None)
    session = MockSession(
        connection_state=ConnectionState.CLOSED,
        filename="/path/to/closed.py",
        session_id="session3",
    )
    app_state = MockAppState({"session3": session})

    result = tool._get_active_sessions_internal(app_state)
    assert result == []


def test_get_active_sessions_internal_no_filename():
    tool = GetActiveNotebooks(app=None)
    session = MockSession(
        connection_state=ConnectionState.OPEN, filename=None, session_id="s4"
    )
    app_state = MockAppState({"s4": session})

    result = tool._get_active_sessions_internal(app_state)
    assert len(result) == 1
    assert result[0].name == "new notebook"
    assert result[0].path == "s4"
    assert result[0].session_id == "s4"


def test_get_active_sessions_internal_multiple_sessions():
    tool = GetActiveNotebooks(app=None)
    sessions = {
        "s1": MockSession(ConnectionState.OPEN, "/path/first.py", "s1"),
        "s2": MockSession(ConnectionState.CLOSED, "/path/closed.py", "s2"),
        "s3": MockSession(ConnectionState.ORPHANED, "/path/third.py", "s3"),
    }
    app_state = MockAppState(sessions)

    with patch(
        "marimo._ai.tools.tools.notebooks.pretty_path"
    ) as mock_pretty_path:
        mock_pretty_path.side_effect = lambda x: os.path.basename(x)
        result = tool._get_active_sessions_internal(app_state)

    assert len(result) == 2
    session_ids = [f.session_id for f in result]
    assert "s3" in session_ids
    assert "s1" in session_ids
    assert "s2" not in session_ids
