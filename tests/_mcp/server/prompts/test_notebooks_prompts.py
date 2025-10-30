import pytest

pytest.importorskip("mcp", reason="MCP requires Python 3.10+")

from unittest.mock import Mock

from marimo._ai._tools.types import MarimoNotebookInfo
from marimo._mcp.server._prompts.prompts.notebooks import ActiveNotebooks
from marimo._types.ids import SessionId


def test_active_notebooks_includes_session_ids_and_paths():
    """Test that essential data (session IDs and file paths) are included."""
    context = Mock()
    context.get_active_sessions_internal.return_value = [
        MarimoNotebookInfo(
            name="notebook.py",
            path="/path/to/notebook.py",
            session_id=SessionId("session_1"),
        ),
        MarimoNotebookInfo(
            name="other.py",
            path="/other/path.py",
            session_id=SessionId("session_2"),
        ),
    ]

    prompt = ActiveNotebooks(context=context)
    messages = prompt.handle()
    text = "\n".join(
        msg.content.text  # type: ignore[attr-defined]
        for msg in messages
        if hasattr(msg.content, "text")
    )

    # Essential data must be present
    assert "session_1" in text
    assert "session_2" in text
    assert "/path/to/notebook.py" in text
    assert "/other/path.py" in text
