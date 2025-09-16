from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import Mock

import pytest

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.cells import (
    CellErrors,
    CellRuntimeMetadata,
    CellVariables,
    CellVariableValue,
    GetCellRuntimeData,
    GetLightweightCellMap,
)
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.ops import VariableValue


@dataclass
class MockCellOp:
    output: object | None = None
    console: object | None = None
    status: object | None = None


@dataclass
class MockOutput:
    channel: object
    data: object


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


@dataclass
class MockSessionView:
    cell_operations: dict | None = None
    last_execution_time: dict | None = None
    variable_values: dict | None = None

    def __post_init__(self) -> None:
        if self.cell_operations is None:
            self.cell_operations = {}
        if self.last_execution_time is None:
            self.last_execution_time = {}
        if self.variable_values is None:
            self.variable_values = {}


@dataclass
class MockSession:
    session_view: MockSessionView


def test_is_markdown_cell():
    tool = GetLightweightCellMap(ToolContext())
    assert tool._is_markdown_cell('mo.md("hi")') is True
    assert tool._is_markdown_cell("print('x')") is False


def test_get_cell_errors_no_cell_op():
    tool = GetCellRuntimeData(ToolContext())
    session = MockSession(MockSessionView())

    result = tool._get_cell_errors(session, "missing")
    assert result == CellErrors(has_errors=False, error_details=None)


def test_get_cell_errors_with_marimo_error():
    tool = GetCellRuntimeData(ToolContext())
    error = MockError(
        "NameError", "name 'x' is not defined", ["line1", "line2"]
    )
    output = MockOutput(CellChannel.MARIMO_ERROR, [error])
    cell_op = MockCellOp(output=output)
    session = MockSession(MockSessionView(cell_operations={"c1": cell_op}))

    result = tool._get_cell_errors(session, "c1")
    assert result.has_errors is True
    assert result.error_details is not None
    assert result.error_details[0].type == "NameError"


def test_get_cell_errors_with_stderr():
    tool = GetCellRuntimeData(ToolContext())
    console_output = MockConsoleOutput(CellChannel.STDERR, "warn")
    cell_op = MockCellOp(console=[console_output])
    session = MockSession(MockSessionView(cell_operations={"c1": cell_op}))

    result = tool._get_cell_errors(session, "c1")
    assert result.has_errors is True
    assert result.error_details is not None
    assert result.error_details[0].type == "STDERR"


def test_get_cell_errors_dict_error():
    tool = GetCellRuntimeData(ToolContext())
    dict_error = {"type": "ValueError", "msg": "invalid", "traceback": ["tb1"]}
    output = MockOutput(CellChannel.MARIMO_ERROR, [dict_error])
    cell_op = MockCellOp(output=output)
    session = MockSession(MockSessionView(cell_operations={"c1": cell_op}))

    result = tool._get_cell_errors(session, "c1")
    assert result.has_errors is True
    assert result.error_details is not None
    assert result.error_details[0].type == "ValueError"


def test_get_cell_metadata_basic():
    tool = GetCellRuntimeData(ToolContext())
    cell_op = MockCellOp(status="idle")
    session = MockSession(
        MockSessionView(
            cell_operations={"c1": cell_op}, last_execution_time={"c1": 42.5}
        )
    )

    result = tool._get_cell_metadata(session, "c1")
    assert result == CellRuntimeMetadata(
        runtime_state="idle", execution_time=42.5
    )


def test_get_cell_metadata_no_cell_op():
    tool = GetCellRuntimeData(ToolContext())
    session = MockSession(MockSessionView())

    result = tool._get_cell_metadata(session, "missing")
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

    var_x = VariableValue("x", 42, "int")
    var_y = VariableValue("y", "hi", "str")
    var_z = VariableValue("z", [1], "list")

    session = MockSession(
        MockSessionView(variable_values={"x": var_x, "y": var_y, "z": var_z})
    )

    result = tool._get_cell_variables(session, cell_data)
    expected: CellVariables = {
        "x": CellVariableValue(
            name="x", value=var_x.value, datatype=var_x.datatype
        ),
        "y": CellVariableValue(
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

    args = GetCellRuntimeDataArgs(session_id="test", cell_id="invalid")

    with pytest.raises(ToolExecutionError) as exc_info:
        tool.handle(args)
    assert exc_info.value.code == "CELL_NOT_FOUND"
