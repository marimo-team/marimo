from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.errors import (
    GetNotebookErrors,
    GetNotebookErrorsArgs,
)
from marimo._ai._tools.types import MarimoCellErrors, MarimoErrorDetail
from marimo._types.ids import CellId_t, SessionId


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
class MockUpdateCellIdsRequest:
    cell_ids: list[str]


@dataclass
class MockSessionView:
    cell_operations: dict | None = None
    cell_ids: MockUpdateCellIdsRequest | None = None

    def __post_init__(self) -> None:
        if self.cell_operations is None:
            self.cell_operations = {}


@dataclass
class DummyAppFileManager:
    app: object


@dataclass
class MockSession:
    session_view: MockSessionView
    app_file_manager: DummyAppFileManager


@pytest.fixture
def tool() -> GetNotebookErrors:
    """Create a GetNotebookErrors tool instance."""
    return GetNotebookErrors(ToolContext())


@pytest.fixture
def mock_context() -> Mock:
    """Create a mock ToolContext."""
    context = Mock(spec=ToolContext)
    return context


def test_get_notebook_errors_empty_session(mock_context: Mock) -> None:
    """Test get_notebook_errors with no errors."""
    mock_context.get_notebook_errors.return_value = []

    tool = GetNotebookErrors(ToolContext())
    tool.context = mock_context

    result = tool.handle(GetNotebookErrorsArgs(session_id=SessionId("s1")))

    assert result.has_errors is False
    assert result.total_errors == 0
    assert result.total_cells_with_errors == 0
    assert result.cells == []
    assert result.next_steps is not None
    assert "No errors detected" in result.next_steps


def test_get_notebook_errors_marimo_error_only(mock_context: Mock) -> None:
    """Test get_notebook_errors with MARIMO_ERROR only."""
    marimo_errors = [
        MarimoCellErrors(
            cell_id=CellId_t("c1"),
            errors=[
                MarimoErrorDetail(
                    type="ValueError",
                    message="bad value",
                    traceback=["line 1"],
                )
            ],
        )
    ]
    mock_context.get_notebook_errors.return_value = marimo_errors

    tool = GetNotebookErrors(ToolContext())
    tool.context = mock_context

    result = tool.handle(GetNotebookErrorsArgs(session_id=SessionId("s1")))

    assert result.has_errors is True
    assert result.total_errors == 1
    assert result.total_cells_with_errors == 1
    assert len(result.cells) == 1
    assert result.cells[0].cell_id == CellId_t("c1")
    assert result.cells[0].errors[0].type == "ValueError"
    assert result.next_steps is not None
    assert "get_cell_runtime_data" in result.next_steps[0]


def test_get_notebook_errors_stderr_only(mock_context: Mock) -> None:
    """Test get_notebook_errors with STDERR only."""
    stderr_errors = [
        MarimoCellErrors(
            cell_id=CellId_t("c2"),
            errors=[
                MarimoErrorDetail(
                    type="STDERR",
                    message="warning message",
                    traceback=[],
                )
            ],
        )
    ]
    mock_context.get_notebook_errors.return_value = stderr_errors

    tool = GetNotebookErrors(ToolContext())
    tool.context = mock_context

    result = tool.handle(GetNotebookErrorsArgs(session_id=SessionId("s1")))

    assert result.has_errors is False
    assert result.total_errors == 0
    assert result.total_cells_with_errors == 1
    assert result.cells[0].errors[0].type == "STDERR"


def test_get_notebook_errors_mixed_errors(mock_context: Mock) -> None:
    """Test get_notebook_errors with both MARIMO_ERROR and STDERR."""
    mixed_errors = [
        MarimoCellErrors(
            cell_id=CellId_t("c1"),
            errors=[
                MarimoErrorDetail(
                    type="ValueError",
                    message="bad value",
                    traceback=["line 1"],
                ),
                MarimoErrorDetail(
                    type="STDERR",
                    message="warn",
                    traceback=[],
                ),
            ],
        )
    ]
    mock_context.get_notebook_errors.return_value = mixed_errors

    tool = GetNotebookErrors(ToolContext())
    tool.context = mock_context

    result = tool.handle(GetNotebookErrorsArgs(session_id=SessionId("s1")))

    assert result.has_errors is True
    assert result.total_errors == 1
    assert result.total_cells_with_errors == 1
    assert len(result.cells[0].errors) == 2


def test_get_notebook_errors_multiple_cells(mock_context: Mock) -> None:
    """Test get_notebook_errors with errors in multiple cells."""
    multiple_errors = [
        MarimoCellErrors(
            cell_id=CellId_t("c1"),
            errors=[
                MarimoErrorDetail(
                    type="ValueError",
                    message="error in c1",
                    traceback=[],
                )
            ],
        ),
        MarimoCellErrors(
            cell_id=CellId_t("c2"),
            errors=[
                MarimoErrorDetail(
                    type="TypeError",
                    message="error in c2",
                    traceback=[],
                )
            ],
        ),
        MarimoCellErrors(
            cell_id=CellId_t("c3"),
            errors=[
                MarimoErrorDetail(
                    type="STDERR",
                    message="stderr in c3",
                    traceback=[],
                )
            ],
        ),
    ]
    mock_context.get_notebook_errors.return_value = multiple_errors

    tool = GetNotebookErrors(ToolContext())
    tool.context = mock_context

    result = tool.handle(GetNotebookErrorsArgs(session_id=SessionId("s1")))

    assert result.has_errors is True
    assert result.total_errors == 2
    assert result.total_cells_with_errors == 3
    assert len(result.cells) == 3


def test_get_notebook_errors_respects_session_id(mock_context: Mock) -> None:
    """Test that get_notebook_errors passes the correct session_id."""
    session_id = SessionId("test-session-123")
    mock_context.get_notebook_errors.return_value = []

    tool = GetNotebookErrors(ToolContext())
    tool.context = mock_context

    tool.handle(GetNotebookErrorsArgs(session_id=session_id))

    # Verify the session_id was passed correctly with include_stderr=True
    mock_context.get_notebook_errors.assert_called_once_with(
        session_id, include_stderr=True
    )
