from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import Mock

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.errors import (
    GetNotebookErrors,
    GetNotebookErrorsArgs,
)
from marimo._messaging.cell_output import CellChannel
from marimo._types.ids import SessionId


@dataclass
class MockCellOp:
    output: object | None = None
    console: object | None = None


@dataclass
class MockOutput:
    channel: object
    data: object


@dataclass
class MockConsoleOutput:
    channel: object
    data: object


@dataclass
class MockSessionView:
    cell_operations: dict | None = None

    def __post_init__(self) -> None:
        if self.cell_operations is None:
            self.cell_operations = {}


@dataclass
class DummyCellData:
    name: str


class DummyCellManager:
    def __init__(self, names: dict[str, str]) -> None:
        self._names = names

    def get_cell_data(self, cell_id: str) -> DummyCellData:
        return DummyCellData(self._names.get(cell_id, cell_id))


@dataclass
class DummyAppFileManager:
    app: object


@dataclass
class MockSession:
    session_view: MockSessionView
    app_file_manager: DummyAppFileManager


def test_collect_errors_none() -> None:
    tool = GetNotebookErrors(ToolContext())

    # Empty session view
    session = MockSession(
        session_view=MockSessionView(),
        app_file_manager=DummyAppFileManager(
            app=Mock(cell_manager=DummyCellManager({}))
        ),
    )

    summaries = tool._collect_errors(session)  # type: ignore[arg-type]
    assert summaries == []


def test_collect_errors_marimo_and_stderr() -> None:
    tool = GetNotebookErrors(ToolContext())

    # Cell c1 has MARIMO_ERROR (dict) and STDERR; c2 has STDERR only
    err_dict = {"type": "ValueError", "msg": "bad value", "traceback": ["tb"]}
    c1 = MockCellOp(
        output=MockOutput(CellChannel.MARIMO_ERROR, [err_dict]),
        console=[MockConsoleOutput(CellChannel.STDERR, "warn")],
    )
    c2 = MockCellOp(console=[MockConsoleOutput(CellChannel.STDERR, "oops")])

    names = {"c1": "Cell 1", "c2": "Cell 2"}
    session = MockSession(
        session_view=MockSessionView(cell_operations={"c1": c1, "c2": c2}),
        app_file_manager=DummyAppFileManager(
            app=Mock(cell_manager=DummyCellManager(names))
        ),
    )

    summaries = tool._collect_errors(session)  # type: ignore[arg-type]

    # Sorted by cell_id: c1 then c2
    assert len(summaries) == 2
    assert summaries[0].cell_id == "c1"
    assert summaries[0].cell_name == "Cell 1"
    assert len(summaries[0].errors) == 2  # one MARIMO_ERROR, one STDERR
    assert summaries[0].errors[0].type == "ValueError"
    assert summaries[1].cell_id == "c2"
    assert summaries[1].cell_name == "Cell 2"
    assert len(summaries[1].errors) == 1
    assert summaries[1].errors[0].type == "STDERR"


def test_handle_integration_uses_context_get_session() -> None:
    tool = GetNotebookErrors(ToolContext())

    c1 = MockCellOp(console=[MockConsoleOutput(CellChannel.STDERR, "warn")])
    session = MockSession(
        session_view=MockSessionView(cell_operations={"c1": c1}),
        app_file_manager=DummyAppFileManager(
            app=Mock(cell_manager=DummyCellManager({"c1": "Cell 1"}))
        ),
    )

    # Mock ToolContext.get_session
    context = Mock(spec=ToolContext)
    context.get_session.return_value = session
    tool.context = context  # type: ignore[assignment]

    out = tool.handle(GetNotebookErrorsArgs(session_id=SessionId("s1")))
    assert out.has_errors is True
    assert out.total_errors == 1
    assert len(out.cells) == 1
    assert out.cells[0].cell_id == "c1"
