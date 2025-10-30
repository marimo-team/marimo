from __future__ import annotations

import os
from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.notebooks import GetActiveNotebooks
from marimo._ai._tools.types import EmptyArgs, MarimoNotebookInfo
from marimo._server.model import ConnectionState
from marimo._types.ids import SessionId


@dataclass
class MockAppFileManager:
    filename: str | None
    path: str | None


@dataclass
class MockSession:
    _connection_state: ConnectionState
    app_file_manager: MockAppFileManager

    def connection_state(self) -> ConnectionState:
        return self._connection_state


@dataclass
class MockSessionManager:
    sessions: dict[str, MockSession]

    def get_active_connection_count(self) -> int:
        return len(
            [
                s
                for s in self.sessions.values()
                if s.connection_state()
                in (ConnectionState.OPEN, ConnectionState.ORPHANED)
            ]
        )


@pytest.fixture
def tool() -> GetActiveNotebooks:
    """Create a GetActiveNotebooks tool instance."""
    return GetActiveNotebooks(ToolContext())


@pytest.fixture
def mock_context() -> Mock:
    """Create a mock ToolContext."""
    context = Mock(spec=ToolContext)
    context.get_active_sessions_internal = (
        ToolContext.get_active_sessions_internal
    )
    return context


def test_get_active_sessions_internal_empty(mock_context: Mock):
    """Test get_active_sessions_internal with no sessions."""
    mock_context.session_manager = MockSessionManager(sessions={})

    result = mock_context.get_active_sessions_internal(mock_context)

    assert result == []


def test_get_active_sessions_internal_open_session(mock_context: Mock):
    """Test get_active_sessions_internal with one open session."""
    session = MockSession(
        _connection_state=ConnectionState.OPEN,
        app_file_manager=MockAppFileManager(
            filename="/path/to/notebook.py",
            path=os.path.abspath("/path/to/notebook.py"),
        ),
    )
    mock_context.session_manager = MockSessionManager(
        sessions={"session1": session}
    )

    result = mock_context.get_active_sessions_internal(mock_context)

    assert len(result) == 1
    assert result[0].name == "notebook.py"
    assert result[0].path == os.path.abspath("/path/to/notebook.py")
    assert result[0].session_id == "session1"


def test_get_active_sessions_internal_orphaned_session(mock_context: Mock):
    """Test get_active_sessions_internal with orphaned session."""
    session = MockSession(
        _connection_state=ConnectionState.ORPHANED,
        app_file_manager=MockAppFileManager(
            filename="/path/to/test.py",
            path=os.path.abspath("/path/to/test.py"),
        ),
    )
    mock_context.session_manager = MockSessionManager(
        sessions={"session2": session}
    )

    result = mock_context.get_active_sessions_internal(mock_context)

    assert len(result) == 1
    assert result[0].name == "test.py"


def test_get_active_sessions_internal_closed_session(mock_context: Mock):
    """Test get_active_sessions_internal filters out closed sessions."""
    session = MockSession(
        _connection_state=ConnectionState.CLOSED,
        app_file_manager=MockAppFileManager(
            filename="/path/to/closed.py",
            path=os.path.abspath("/path/to/closed.py"),
        ),
    )
    mock_context.session_manager = MockSessionManager(
        sessions={"session3": session}
    )

    result = mock_context.get_active_sessions_internal(mock_context)

    assert result == []


def test_get_active_sessions_internal_no_filename(mock_context: Mock):
    """Test get_active_sessions_internal with unsaved notebook."""
    session = MockSession(
        _connection_state=ConnectionState.OPEN,
        app_file_manager=MockAppFileManager(filename=None, path=None),
    )
    mock_context.session_manager = MockSessionManager(sessions={"s4": session})

    result = mock_context.get_active_sessions_internal(mock_context)

    assert len(result) == 1
    assert result[0].name == "new notebook"
    assert (
        result[0].path == "(unsaved notebook - save to disk to get file path)"
    )
    assert result[0].session_id == "s4"


def test_get_active_sessions_internal_multiple_sessions(mock_context: Mock):
    """Test get_active_sessions_internal with multiple sessions of different states."""
    sessions = {
        "s1": MockSession(
            ConnectionState.OPEN,
            MockAppFileManager(
                "/path/first.py", os.path.abspath("/path/first.py")
            ),
        ),
        "s2": MockSession(
            ConnectionState.CLOSED,
            MockAppFileManager(
                "/path/closed.py", os.path.abspath("/path/closed.py")
            ),
        ),
        "s3": MockSession(
            ConnectionState.ORPHANED,
            MockAppFileManager(
                "/path/third.py", os.path.abspath("/path/third.py")
            ),
        ),
    }
    mock_context.session_manager = MockSessionManager(sessions=sessions)

    result = mock_context.get_active_sessions_internal(mock_context)

    assert len(result) == 2
    session_ids = [f.session_id for f in result]
    assert "s3" in session_ids
    assert "s1" in session_ids
    assert "s2" not in session_ids


def test_get_active_notebooks_handle(tool: GetActiveNotebooks):
    """Test GetActiveNotebooks.handle() end-to-end."""
    session = MockSession(
        ConnectionState.OPEN,
        MockAppFileManager(
            "/test/notebook.py", os.path.abspath("/test/notebook.py")
        ),
    )
    session_manager = MockSessionManager(sessions={"session1": session})

    # Mock the context
    context = Mock(spec=ToolContext)
    context.session_manager = session_manager
    context.get_active_sessions_internal = Mock(
        return_value=[
            MarimoNotebookInfo(
                name="notebook.py",
                path="/test/notebook.py",
                session_id=SessionId("session1"),
            )
        ]
    )
    tool.context = context

    result = tool.handle(EmptyArgs())

    assert result.status == "success"
    assert result.data.summary.total_notebooks == 1
    assert result.data.summary.active_connections == 1
    assert len(result.data.notebooks) == 1
