import pytest

pytest.importorskip("mcp", reason="MCP requires Python 3.10+")

from unittest.mock import Mock

from marimo._mcp.server._prompts.prompts.notebooks import ActiveNotebooks
from marimo._server.sessions import Session


def test_active_notebooks_metadata():
    """Test that name and description are properly set."""
    prompt = ActiveNotebooks(context=Mock())
    assert prompt.name == "active_notebooks"
    assert (
        prompt.description
        == "Get current active notebooks and their session IDs and file paths."
    )


def test_active_notebooks_no_sessions():
    """Test output when no sessions are active."""
    context = Mock()
    context.session_manager.sessions = {}

    prompt = ActiveNotebooks(context=context)
    messages = prompt.handle()

    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content.type == "text"
    assert (
        "No active marimo notebook sessions found" in messages[0].content.text
    )


def test_active_notebooks_with_sessions():
    """Test output with active sessions."""
    context = Mock()

    # Mock session with file path
    session1 = Mock(spec=Session)
    session1.app_file_manager = Mock()
    session1.app_file_manager.filename = "/path/to/notebook.py"

    # Mock session without file path
    session2 = Mock(spec=Session)
    session2.app_file_manager = Mock()
    session2.app_file_manager.filename = None

    context.session_manager.sessions = {
        "session_1": session1,
        "session_2": session2,
    }

    prompt = ActiveNotebooks(context=context)
    messages = prompt.handle()

    assert len(messages) == 2

    # Check first message (with file path)
    assert messages[0].role == "user"
    assert messages[0].content.type == "text"
    assert "session_1" in messages[0].content.text
    assert "/path/to/notebook.py" in messages[0].content.text
    assert (
        "Use this session_id when calling MCP tools"
        in messages[0].content.text
    )

    # Check second message (without file path)
    assert messages[1].role == "user"
    assert messages[1].content.type == "text"
    assert "session_2" in messages[1].content.text
    assert (
        "Use this session_id when calling MCP tools"
        in messages[1].content.text
    )
