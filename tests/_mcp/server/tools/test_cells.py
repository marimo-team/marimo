"""Tests for marimo._mcp.server.tools.cells module."""

from unittest.mock import Mock

import pytest

# Skip all MCP tests if Python < 3.10 or MCP not available
pytest.importorskip("mcp", reason="MCP requires Python 3.10+")


from marimo._mcp.server.tools.cells import (
    CellErrors,
    CellRuntimeMetadata,
    CellType,
    CellVariables,
    _determine_cell_type,
    _get_cell_errors,
    _get_cell_metadata,
    _get_cell_variables,
)
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.ops import VariableValue


class MockCellOp:
    """Mock CellOp for testing."""

    def __init__(self, output=None, console=None, status=None):
        self.output = output
        self.console = console
        self.status = status


class MockOutput:
    """Mock output for testing."""

    def __init__(self, channel, data):
        self.channel = channel
        self.data = data


class MockConsoleOutput:
    """Mock console output for testing."""

    def __init__(self, channel, data):
        self.channel = channel
        self.data = data


class MockError:
    """Mock error object for testing."""

    def __init__(self, error_type, message, traceback=None):
        self.type = error_type
        self._message = message
        self.traceback = traceback or []

    def describe(self):
        return self._message


class MockSessionView:
    """Mock session view for testing."""

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
    """Mock session for testing."""

    def __init__(self, session_view):
        self.session_view = session_view


class MockCell:
    """Mock cell for testing."""

    def __init__(self, language="python", defs=None):
        self._cell = Mock()
        self._cell.language = language
        self._cell.defs = defs or set()


def test_determine_cell_type_default():
    """Test _determine_cell_type defaults to CODE."""
    result = _determine_cell_type("print('hello')")
    assert result == CellType.CODE


def test_determine_cell_type_with_sql_cell():
    """Test _determine_cell_type with SQL cell."""
    cell = MockCell(language="sql")

    result = _determine_cell_type("SELECT * FROM table", cell)
    assert result == CellType.SQL


def test_determine_cell_type_with_python_cell():
    """Test _determine_cell_type with Python cell."""
    cell = MockCell(language="python")

    result = _determine_cell_type("x = 1", cell)
    assert result == CellType.CODE


def test_determine_markdown_cell():
    """Test _determine_cell_type with Markdown cell."""
    cell = MockCell(language="python")
    result = _determine_cell_type("mo.md('Hello, world!')", cell)
    assert result == CellType.MARKDOWN


def test_get_cell_errors_no_cell_op():
    """Test _get_cell_errors when no cell operation exists."""
    session_view = MockSessionView()
    session = MockSession(session_view)

    result = _get_cell_errors(session, "nonexistent_cell")

    expected: CellErrors = {"has_errors": False, "error_details": None}
    assert result == expected


def test_get_cell_errors_with_marimo_error():
    """Test _get_cell_errors with marimo error."""
    error = MockError(
        "NameError", "name 'x' is not defined", ["line 1", "line 2"]
    )
    output = MockOutput(CellChannel.MARIMO_ERROR, [error])
    cell_op = MockCellOp(output=output)

    session_view = MockSessionView(cell_operations={"cell1": cell_op})
    session = MockSession(session_view)

    result = _get_cell_errors(session, "cell1")

    assert result["has_errors"] is True
    assert len(result["error_details"]) == 1
    assert result["error_details"][0]["type"] == "NameError"
    assert result["error_details"][0]["message"] == "name 'x' is not defined"
    assert result["error_details"][0]["traceback"] == ["line 1", "line 2"]


def test_get_cell_errors_with_stderr():
    """Test _get_cell_errors with STDERR output."""
    console_output = MockConsoleOutput(
        CellChannel.STDERR, "Warning: deprecated function"
    )
    cell_op = MockCellOp(console=[console_output])

    session_view = MockSessionView(cell_operations={"cell1": cell_op})
    session = MockSession(session_view)

    result = _get_cell_errors(session, "cell1")

    assert result["has_errors"] is True
    assert len(result["error_details"]) == 1
    assert result["error_details"][0]["type"] == "STDERR"
    assert (
        result["error_details"][0]["message"] == "Warning: deprecated function"
    )
    assert result["error_details"][0]["traceback"] == []


def test_get_cell_errors_dict_error():
    """Test _get_cell_errors with dict-based error."""
    dict_error = {
        "type": "ValueError",
        "msg": "invalid value",
        "traceback": ["tb1"],
    }
    output = MockOutput(CellChannel.MARIMO_ERROR, [dict_error])
    cell_op = MockCellOp(output=output)

    session_view = MockSessionView(cell_operations={"cell1": cell_op})
    session = MockSession(session_view)

    result = _get_cell_errors(session, "cell1")

    assert result["has_errors"] is True
    assert result["error_details"][0]["type"] == "ValueError"
    assert result["error_details"][0]["message"] == "invalid value"
    assert result["error_details"][0]["traceback"] == ["tb1"]


def test_get_cell_metadata_basic():
    """Test _get_cell_metadata basic functionality."""
    cell_op = MockCellOp(status="idle")
    session_view = MockSessionView(
        cell_operations={"cell1": cell_op}, last_execution_time={"cell1": 42.5}
    )
    session = MockSession(session_view)

    result = _get_cell_metadata(session, "cell1")

    expected: CellRuntimeMetadata = {
        "runtime_state": "idle",
        "execution_time": 42.5,
    }
    assert result == expected


def test_get_cell_metadata_no_cell_op():
    """Test _get_cell_metadata when no cell operation exists."""
    session_view = MockSessionView()
    session = MockSession(session_view)

    result = _get_cell_metadata(session, "nonexistent")

    expected: CellRuntimeMetadata = {
        "runtime_state": None,
        "execution_time": None,
    }
    assert result == expected


def test_get_cell_variables_no_cell_data():
    """Test _get_cell_variables with no cell data."""
    session = MockSession(MockSessionView())

    result = _get_cell_variables(session, None)

    assert result == {}


def test_get_cell_variables_with_variables():
    """Test _get_cell_variables with actual variables."""
    # Mock cell with defined variables
    cell = MockCell(defs={"x", "y"})
    cell_data = Mock()
    cell_data.cell = cell

    # Mock variable values
    var_x = VariableValue("x", 42, "int")
    var_y = VariableValue("y", "hello", "str")
    var_z = VariableValue("z", [1, 2, 3], "list")  # Not defined by this cell

    session_view = MockSessionView(
        variable_values={"x": var_x, "y": var_y, "z": var_z}
    )
    session = MockSession(session_view)

    result = _get_cell_variables(session, cell_data)

    expected: CellVariables = {"x": var_x, "y": var_y}
    assert result == expected
    assert (
        "z" not in result
    )  # Should not include variables not defined by this cell


def test_get_cell_variables_missing_variables():
    """Test _get_cell_variables when some defined variables are missing from session."""
    cell = MockCell(defs={"x", "y", "z"})
    cell_data = Mock()
    cell_data.cell = cell

    # Only some variables are available in session
    var_x = VariableValue("x", 1, "int")
    session_view = MockSessionView(variable_values={"x": var_x})
    session = MockSession(session_view)

    result = _get_cell_variables(session, cell_data)

    # Should only include variables that exist in session
    expected: CellVariables = {"x": var_x}
    assert result == expected
