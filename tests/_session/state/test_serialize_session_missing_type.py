from __future__ import annotations

from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.notification import CellNotification
from marimo._session.state.serialize import serialize_session_view
from marimo._session.state.session_view import SessionView
from marimo._types.ids import CellId_t

CELL_ID = CellId_t("cell1")


def test_serialize_session_with_dict_error_missing_type():
    """Test serialization of a session with a dictionary error missing the type key"""
    view = SessionView()
    view.cell_notifications[CELL_ID] = CellNotification(
        cell_id=CELL_ID,
        status="idle",
        output=CellOutput(
            channel=CellChannel.MARIMO_ERROR,
            mimetype="text/plain",
            data=[
                {"msg": "Something went wrong"}
            ],  # Dictionary with missing type key
        ),
        console=[],
        timestamp=0,
    )
    view.last_executed_code[CELL_ID] = (
        "raise RuntimeError('Something went wrong')"
    )

    result = serialize_session_view(
        view, cell_ids=[CELL_ID], drop_virtual_file_outputs=False
    )
    assert len(result["cells"]) == 1
    assert len(result["cells"][0]["outputs"]) == 1
    assert result["cells"][0]["outputs"][0]["type"] == "error"
    assert result["cells"][0]["outputs"][0]["ename"] == "UnknownError"
    assert result["cells"][0]["outputs"][0]["evalue"] == "Something went wrong"
