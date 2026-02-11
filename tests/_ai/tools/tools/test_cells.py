from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import Mock

import pytest

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.cells import (
    CellRuntimeMetadata,
    CellVariables,
    GetCellOutputArgs,
    GetCellOutputs,
    GetCellRuntimeData,
    GetCellRuntimeDataArgs,
    GetLightweightCellMap,
    GetLightweightCellMapArgs,
)
from marimo._ai._tools.types import MarimoCellConsoleOutputs
from marimo._ai._tools.utils.exceptions import ToolExecutionError
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
    cell_notification = MockCellNotification(status="idle")
    session = MockSession(
        _session_view=MockSessionView(
            cell_notifications={"c1": cell_notification},
            last_execution_time={"c1": 42.5},
        )
    )

    result = tool._get_cell_metadata(session, CellId_t("c1"))
    assert result == CellRuntimeMetadata(
        runtime_state="idle", execution_time=42.5
    )


def test_get_cell_metadata_no_cell_notification():
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

    args = GetCellRuntimeDataArgs(
        session_id=SessionId("test"), cell_ids=[CellId_t("invalid")]
    )

    with pytest.raises(ToolExecutionError) as exc_info:
        tool.handle(args)
    assert exc_info.value.code == "CELL_NOT_FOUND"


def test_get_cell_runtime_data_empty_cell_ids():
    """Test GetCellRuntimeData with empty cell_ids returns empty data."""
    tool = GetCellRuntimeData(ToolContext())

    mock_session = Mock()
    context = Mock(spec=ToolContext)
    context.get_session.return_value = mock_session
    tool.context = context

    args = GetCellRuntimeDataArgs(session_id=SessionId("test"), cell_ids=[])
    result = tool.handle(args)
    assert result.data == []


def test_get_cell_outputs_empty_cell_ids():
    """Test GetCellOutputs with empty cell_ids returns empty cells."""
    tool = GetCellOutputs(ToolContext())

    mock_session = Mock()
    context = Mock(spec=ToolContext)
    context.get_session.return_value = mock_session
    tool.context = context

    args = GetCellOutputArgs(session_id=SessionId("test"), cell_ids=[])
    result = tool.handle(args)
    assert result.cells == []


def test_get_visual_output_with_html():
    tool = GetCellOutputs(ToolContext())
    output = MockOutput(data="<div>test</div>", mimetype="text/html")
    cell_notification = MockCellNotification(output=output)

    visual_output, mimetype = tool._get_visual_output(cell_notification)  # type: ignore[arg-type]
    assert visual_output == "<div>test</div>"
    assert mimetype == "text/html"


def test_get_visual_output_no_output():
    tool = GetCellOutputs(ToolContext())
    cell_notification = MockCellNotification(output=None)

    visual_output, mimetype = tool._get_visual_output(cell_notification)  # type: ignore[arg-type]
    assert visual_output is None
    assert mimetype is None


def test_lightweight_cell_map_includes_runtime_info():
    """Test that LightweightCellInfo includes runtime_state, has_output,
    and has_console_output from cell notifications."""
    tool = GetLightweightCellMap(ToolContext())

    # Mock cell data
    cell_data_1 = Mock()
    cell_data_1.cell_id = "c1"
    cell_data_1.code = "x = 1"
    cell_data_1.cell = None  # no compiled cell

    cell_data_2 = Mock()
    cell_data_2.cell_id = "c2"
    cell_data_2.code = "print('hello')"
    cell_data_2.cell = None

    cell_data_3 = Mock()
    cell_data_3.cell_id = "c3"
    cell_data_3.code = "y = 2"
    cell_data_3.cell = None

    # Mock cell manager
    mock_cell_manager = Mock()
    mock_cell_manager.cell_data.return_value = [
        cell_data_1,
        cell_data_2,
        cell_data_3,
    ]

    # Cell notifications: c1 is idle with output, c2 is running with console output, c3 has no notification
    notif_c1 = MockCellNotification(
        status="idle",
        output=MockOutput(data="42", mimetype="text/plain"),
        console=None,
    )
    notif_c2 = MockCellNotification(
        status="running",
        output=None,
        console=[MockConsoleOutput(channel="stdout", data="hello")],
    )

    mock_session = Mock()
    mock_session.app_file_manager.app.cell_manager = mock_cell_manager
    mock_session.app_file_manager.filename = "test.py"
    mock_session.session_view = MockSessionView(
        cell_notifications={"c1": notif_c1, "c2": notif_c2}
    )

    context = Mock(spec=ToolContext)
    context.get_session.return_value = mock_session
    tool.context = context

    args = GetLightweightCellMapArgs(
        session_id=SessionId("test"), preview_lines=3
    )
    result = tool.handle(args)

    assert len(result.cells) == 3

    # c1: idle, has output, no console output
    assert result.cells[0].cell_id == "c1"
    assert result.cells[0].runtime_state == "idle"
    assert result.cells[0].has_output is True
    assert result.cells[0].has_console_output is False

    # c2: running, no output, has console output
    assert result.cells[1].cell_id == "c2"
    assert result.cells[1].runtime_state == "running"
    assert result.cells[1].has_output is False
    assert result.cells[1].has_console_output is True

    # c3: no notification at all
    assert result.cells[2].cell_id == "c3"
    assert result.cells[2].runtime_state is None
    assert result.cells[2].has_output is False
    assert result.cells[2].has_console_output is False


def test_get_cell_runtime_data_batched():
    """Test GetCellRuntimeData with multiple cell IDs."""
    tool = GetCellRuntimeData(ToolContext())

    # Mock two cells
    cell_data_1 = Mock()
    cell_data_1.code = "x = 1"
    cell_data_1.cell = None

    cell_data_2 = Mock()
    cell_data_2.code = "y = 2"
    cell_data_2.cell = None

    mock_cell_manager = Mock()
    mock_cell_manager.get_cell_data.side_effect = lambda cid: (
        cell_data_1 if cid == "c1" else cell_data_2
    )

    notif_c1 = MockCellNotification(status="idle")
    notif_c2 = MockCellNotification(status="running")

    mock_session = Mock()
    mock_session.app_file_manager.app.cell_manager = mock_cell_manager
    mock_session.session_view = MockSessionView(
        cell_notifications={"c1": notif_c1, "c2": notif_c2},
        last_execution_time={"c1": 10.0, "c2": 20.0},
    )

    context = Mock(spec=ToolContext)
    context.get_session.return_value = mock_session
    context.get_cell_errors.return_value = []
    tool.context = context

    args = GetCellRuntimeDataArgs(
        session_id=SessionId("test"),
        cell_ids=[CellId_t("c1"), CellId_t("c2")],
    )
    result = tool.handle(args)

    assert len(result.data) == 2
    assert result.data[0].cell_id == "c1"
    assert result.data[0].code == "x = 1"
    assert result.data[0].metadata.runtime_state == "idle"  # type: ignore[union-attr]
    assert result.data[0].metadata.execution_time == 10.0  # type: ignore[union-attr]
    assert result.data[1].cell_id == "c2"
    assert result.data[1].code == "y = 2"
    assert result.data[1].metadata.runtime_state == "running"  # type: ignore[union-attr]
    assert result.data[1].metadata.execution_time == 20.0  # type: ignore[union-attr]


def test_get_cell_outputs_batched():
    """Test GetCellOutputs with multiple cell IDs."""
    tool = GetCellOutputs(ToolContext())

    notif_c1 = MockCellNotification(
        output=MockOutput(data="<b>hi</b>", mimetype="text/html"),
        console=None,
    )
    notif_c2 = MockCellNotification(output=None, console=None)

    mock_session = Mock()
    mock_session.session_view = MockSessionView(
        cell_notifications={"c1": notif_c1, "c2": notif_c2}
    )

    context = Mock(spec=ToolContext)
    context.get_session.return_value = mock_session
    context.get_cell_console_outputs.return_value = MarimoCellConsoleOutputs()
    tool.context = context

    args = GetCellOutputArgs(
        session_id=SessionId("test"),
        cell_ids=[CellId_t("c1"), CellId_t("c2")],
    )
    result = tool.handle(args)

    assert len(result.cells) == 2
    assert result.cells[0].cell_id == "c1"
    assert result.cells[0].visual_output.visual_output == "<b>hi</b>"
    assert result.cells[0].visual_output.visual_mimetype == "text/html"
    assert result.cells[1].cell_id == "c2"
    assert result.cells[1].visual_output.visual_output is None


def test_get_cell_outputs_invalid_cell():
    """Test GetCellOutputs raises for unknown cell ID."""
    tool = GetCellOutputs(ToolContext())

    mock_session = Mock()
    mock_session.session_view = MockSessionView(cell_notifications={})

    context = Mock(spec=ToolContext)
    context.get_session.return_value = mock_session
    tool.context = context

    args = GetCellOutputArgs(
        session_id=SessionId("test"),
        cell_ids=[CellId_t("missing")],
    )

    with pytest.raises(ToolExecutionError) as exc_info:
        tool.handle(args)
    assert exc_info.value.code == "CELL_NOT_FOUND"
