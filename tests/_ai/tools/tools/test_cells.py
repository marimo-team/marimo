from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import Mock

import pytest

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.cells import (
    CellRuntimeMetadata,
    CellVariables,
    GetCellOutputs,
    GetCellRuntimeData,
    GetLightweightCellMap,
)
from marimo._messaging.notification import VariableValue
from marimo._types.ids import CellId_t, SessionId
from tests._ai.tools.test_utils import MockSession, MockSessionView


@dataclass
class MockCellNotification:
    output: object | None = None
    console: object | None = None
    status: object | None = None


@dataclass
class MockOutput:
    channel: object = None
    data: object = None
    mimetype: object = None


@dataclass
class MockConsoleOutput:
    channel: object
    data: object


@dataclass
class MockError:
    type: str
    _message: str
    traceback: list[str] = field(default_factory=list)

    def describe(self) -> str:
        return self._message


def test_is_markdown_cell():
    tool = GetLightweightCellMap(ToolContext())
    assert tool._is_markdown_cell('mo.md("hi")') is True
    assert tool._is_markdown_cell("print('x')") is False


def test_get_cell_metadata_basic():
    tool = GetCellRuntimeData(ToolContext())
    cell_op = MockCellNotification(status="idle")
    session = MockSession(
        _session_view=MockSessionView(
            cell_operations={"c1": cell_op}, last_execution_time={"c1": 42.5}
        )
    )

    result = tool._get_cell_metadata(session, CellId_t("c1"))
    assert result == CellRuntimeMetadata(
        runtime_state="idle", execution_time=42.5
    )


def test_get_cell_metadata_no_cell_op():
    tool = GetCellRuntimeData(ToolContext())
    session = MockSession(_session_view=MockSessionView())

    result = tool._get_cell_metadata(session, CellId_t("missing"))
    assert result == CellRuntimeMetadata(
        runtime_state=None, execution_time=None
    )


def test_get_cell_variables():
    tool = GetCellRuntimeData(ToolContext())
    cell = Mock()
    cell._cell = Mock()
    cell._cell.defs = {"x", "y"}
    cell_data = Mock()
    cell_data.cell = cell

    var_x = VariableValue("x", "42", "int")
    var_y = VariableValue("y", "hi", "str")
    var_z = VariableValue("z", "[1]", "list")

    session = MockSession(
        _session_view=MockSessionView(
            variable_values={"x": var_x, "y": var_y, "z": var_z}
        )
    )

    result = tool._get_cell_variables(session, cell_data)
    expected: CellVariables = {
        "x": VariableValue(
            name="x", value=var_x.value, datatype=var_x.datatype
        ),
        "y": VariableValue(
            name="y", value=var_y.value, datatype=var_y.datatype
        ),
    }
    assert result == expected
    assert "z" not in result


def test_get_cell_type_sql():
    """Test _get_cell_type for SQL cells."""
    tool = GetLightweightCellMap(ToolContext())

    # Mock cell with SQL language
    cell_mock = Mock()
    cell_mock._cell = Mock()
    cell_mock._cell.language = "sql"

    cell_data = Mock()
    cell_data.cell = cell_mock
    cell_data.code = "SELECT * FROM table"

    result = tool._get_cell_type(cell_data)
    assert result == "sql"


def test_get_cell_runtime_data_invalid_cell():
    """Test GetCellRuntimeData with invalid cell ID."""
    tool = GetCellRuntimeData(ToolContext())

    # Mock cell manager that returns None
    mock_cell_manager = Mock()
    mock_cell_manager.get_cell_data.return_value = None

    mock_session = Mock()
    mock_session.app_file_manager.app.cell_manager = mock_cell_manager

    context = Mock(spec=ToolContext)
    context.get_session.return_value = mock_session
    tool.context = context

    from marimo._ai._tools.tools.cells import GetCellRuntimeDataArgs
    from marimo._ai._tools.utils.exceptions import ToolExecutionError

    args = GetCellRuntimeDataArgs(
        session_id=SessionId("test"), cell_id=CellId_t("invalid")
    )

    with pytest.raises(ToolExecutionError) as exc_info:
        tool.handle(args)
    assert exc_info.value.code == "CELL_NOT_FOUND"


def test_get_visual_output_with_html():
    tool = GetCellOutputs(ToolContext())
    output = MockOutput(data="<div>test</div>", mimetype="text/html")
    cell_op = MockCellNotification(output=output)

    visual_output, mimetype = tool._get_visual_output(cell_op)  # type: ignore[arg-type]
    assert visual_output == "<div>test</div>"
    assert mimetype == "text/html"


def test_get_visual_output_no_output():
    tool = GetCellOutputs(ToolContext())
    cell_op = MockCellNotification(output=None)

    visual_output, mimetype = tool._get_visual_output(cell_op)  # type: ignore[arg-type]
    assert visual_output is None
    assert mimetype is None
