import pytest

pytest.importorskip("mcp", reason="MCP requires Python 3.10+")

from unittest.mock import Mock

from marimo._mcp.server._prompts.prompts.notebooks import ActiveNotebooks


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
    context.get_active_sessions_internal.return_value = []

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

    # Mock active session objects
    active_session1 = Mock()
    active_session1.session_id = "session_1"
    active_session1.path = "/path/to/notebook.py"

    active_session2 = Mock()
    active_session2.session_id = "session_2"
    active_session2.path = None

    context.get_active_sessions_internal.return_value = [
        active_session1,
        active_session2,
    ]

    prompt = ActiveNotebooks(context=context)
    messages = prompt.handle()

    assert len(messages) == 3  # 2 sessions + 1 action message

    # Check first message (with file path)
    assert messages[0].role == "user"
    assert messages[0].content.type == "text"
    assert "session_1" in messages[0].content.text
    assert "/path/to/notebook.py" in messages[0].content.text

    # Check second message (without file path)
    assert messages[1].role == "user"
    assert messages[1].content.type == "text"
    assert "session_2" in messages[1].content.text

    # Check action message
    assert messages[2].role == "user"
    assert messages[2].content.type == "text"
    assert (
        "Use these session_ids when calling marimo MCP tools"
        in messages[2].content.text
    )
