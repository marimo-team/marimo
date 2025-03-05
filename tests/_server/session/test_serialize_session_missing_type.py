from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.ops import CellOp
from marimo._server.session.serialize import serialize_session_view
from marimo._server.session.session_view import SessionView


def test_serialize_session_with_dict_error_missing_type():
    """Test serialization of a session with a dictionary error missing the type key"""
    view = SessionView()
    view.cell_operations["cell1"] = CellOp(
        cell_id="cell1",
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
    view.last_executed_code["cell1"] = (
        "raise RuntimeError('Something went wrong')"
    )

    result = serialize_session_view(view)
    assert len(result["cells"]) == 1
    assert len(result["cells"][0]["outputs"]) == 1
    assert result["cells"][0]["outputs"][0]["type"] == "error"
    assert result["cells"][0]["outputs"][0]["ename"] == "Unknown"
    assert result["cells"][0]["outputs"][0]["evalue"] == "Something went wrong"
