from __future__ import annotations

from unittest.mock import Mock

from marimo._ai.tools.tools.cells import (
    GetCellRuntimeData,
    GetLightweightCellMap,
)
from marimo._ai.tools.types import (
    CellErrors,
    CellRuntimeMetadata,
    CellVariables,
    CellVariableValue,
)
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.ops import VariableValue


class MockCellOp:
    def __init__(self, output=None, console=None, status=None):
        self.output = output
        self.console = console
        self.status = status


class MockOutput:
    def __init__(self, channel, data):
        self.channel = channel
        self.data = data


class MockConsoleOutput:
    def __init__(self, channel, data):
        self.channel = channel
        self.data = data


class MockError:
    def __init__(self, error_type, message, traceback=None):
        self.type = error_type
        self._message = message
        self.traceback = traceback or []

    def describe(self):
        return self._message


class MockSessionView:
    def __init__(
        self,
        cell_operations=None,
        last_execution_time=None,
        variable_values=None,
    ):
        self.cell_operations = cell_operations or {}
        self.last_execution_time = last_execution_time or {}
        self.variable_values = variable_values or {}


class MockSession:
    def __init__(self, session_view):
        self.session_view = session_view


def test_is_markdown_cell():
    tool = GetLightweightCellMap(app=None)
    assert tool._is_markdown_cell('mo.md("hi")') is True
    assert tool._is_markdown_cell("print('x')") is False


def test_get_cell_errors_no_cell_op():
    tool = GetCellRuntimeData(app=None)
    session = MockSession(MockSessionView())

    result = tool._get_cell_errors(session, "missing")
    assert result == CellErrors(has_errors=False, error_details=None)


def test_get_cell_errors_with_marimo_error():
    tool = GetCellRuntimeData(app=None)
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
    tool = GetCellRuntimeData(app=None)
    console_output = MockConsoleOutput(CellChannel.STDERR, "warn")
    cell_op = MockCellOp(console=[console_output])
    session = MockSession(MockSessionView(cell_operations={"c1": cell_op}))

    result = tool._get_cell_errors(session, "c1")
    assert result.has_errors is True
    assert result.error_details is not None
    assert result.error_details[0].type == "STDERR"


def test_get_cell_errors_dict_error():
    tool = GetCellRuntimeData(app=None)
    dict_error = {"type": "ValueError", "msg": "invalid", "traceback": ["tb1"]}
    output = MockOutput(CellChannel.MARIMO_ERROR, [dict_error])
    cell_op = MockCellOp(output=output)
    session = MockSession(MockSessionView(cell_operations={"c1": cell_op}))

    result = tool._get_cell_errors(session, "c1")
    assert result.has_errors is True
    assert result.error_details is not None
    assert result.error_details[0].type == "ValueError"


def test_get_cell_metadata_basic():
    tool = GetCellRuntimeData(app=None)
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
    tool = GetCellRuntimeData(app=None)
    session = MockSession(MockSessionView())

    result = tool._get_cell_metadata(session, "missing")
    assert result == CellRuntimeMetadata(
        runtime_state=None, execution_time=None
    )


def test_get_cell_variables():
    tool = GetCellRuntimeData(app=None)
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
