import pytest

pytest.importorskip("mcp", reason="MCP requires Python 3.10+")

from unittest.mock import Mock

from marimo._ai._tools.types import (
    MarimoCellErrors,
    MarimoErrorDetail,
    MarimoNotebookInfo,
)
from marimo._mcp.server._prompts.prompts.errors import ErrorsSummary
from marimo._types.ids import CellId_t, SessionId


def test_errors_summary_includes_essential_data():
    """Test that essential data (notebook info, cell IDs, error messages) are included."""
    context = Mock()
    context.get_active_sessions_internal.return_value = [
        MarimoNotebookInfo(
            name="notebook.py",
            path="/path/to/notebook.py",
            session_id=SessionId("session_1"),
        )
    ]
    context.get_notebook_errors.return_value = [
        MarimoCellErrors(
            cell_id=CellId_t("cell_1"),
            errors=[
                MarimoErrorDetail(
                    type="ValueError",
                    message="invalid value",
                    traceback=["line 1"],
                )
            ],
        ),
        MarimoCellErrors(
            cell_id=CellId_t("cell_2"),
            errors=[
                MarimoErrorDetail(
                    type="TypeError",
                    message="wrong type",
                    traceback=["line 2"],
                )
            ],
        ),
    ]

    prompt = ErrorsSummary(context=context)
    messages = prompt.handle()
    text = "\n".join(
        msg.content.text  # type: ignore[attr-defined]
        for msg in messages
        if hasattr(msg.content, "text")
    )

    # Essential data must be present
    assert "notebook.py" in text
    assert "session_1" in text
    assert "/path/to/notebook.py" in text
    assert "cell_1" in text
    assert "cell_2" in text
    assert "ValueError" in text
    assert "invalid value" in text
    assert "TypeError" in text
    assert "wrong type" in text

