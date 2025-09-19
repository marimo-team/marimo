# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from marimo import _loggers
from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.tools.cells import ErrorDetail
from marimo._ai._tools.types import SuccessResult
from marimo._server.sessions import Session
from marimo._types.ids import CellId_t, SessionId

LOGGER = _loggers.marimo_logger()


@dataclass
class GetNotebookErrorsArgs:
    session_id: SessionId


@dataclass
class CellErrorsSummary:
    cell_id: CellId_t
    errors: list[ErrorDetail] = field(default_factory=list)


@dataclass
class GetNotebookErrorsOutput(SuccessResult):
    has_errors: bool = False
    total_errors: int = 0
    cells: list[CellErrorsSummary] = field(default_factory=list)


class GetNotebookErrors(
    ToolBase[GetNotebookErrorsArgs, GetNotebookErrorsOutput]
):
    """
    Get all errors in the current notebook session, organized by cell.

    Args:
        session_id: The session ID of the notebook.

    Returns:
        A success result containing per-cell error details and totals.
    """

    def handle(self, args: GetNotebookErrorsArgs) -> GetNotebookErrorsOutput:
        session = self.context.get_session(args.session_id)
        summaries = self._collect_errors(session)

        total_errors = sum(len(s.errors) for s in summaries)
        has_errors = total_errors > 0

        return GetNotebookErrorsOutput(
            has_errors=has_errors,
            total_errors=total_errors,
            cells=summaries,
            next_steps=(
                [
                    "Use get_cell_runtime_data to inspect the impacted cells to fix syntax/runtime issues",
                    "Re-run the notebook after addressing the errors",
                ]
                if has_errors
                else ["No errors detected"]
            ),
        )

    # helpers
    def _collect_errors(self, session: Session) -> list[CellErrorsSummary]:
        from marimo._messaging.cell_output import CellChannel

        session_view = session.session_view

        summaries: list[CellErrorsSummary] = []
        for cell_id, cell_op in session_view.cell_operations.items():
            errors: list[ErrorDetail] = []

            # Collect structured marimo errors from output
            if (
                cell_op.output
                and cell_op.output.channel == CellChannel.MARIMO_ERROR
            ):
                items = cell_op.output.data
                if isinstance(items, list):
                    for err in items:
                        if isinstance(err, dict):
                            errors.append(
                                ErrorDetail(
                                    type=err.get("type", "UnknownError"),
                                    message=err.get("msg", str(err)),
                                    traceback=err.get("traceback", []),
                                )
                            )
                        else:
                            # Fallback for rich error objects
                            err_type: str = getattr(
                                err, "type", type(err).__name__
                            )
                            describe_fn: Optional[Any] = getattr(
                                err, "describe", None
                            )
                            message_val = (
                                describe_fn()
                                if callable(describe_fn)
                                else str(err)
                            )
                            message: str = str(message_val)
                            tb: list[str] = getattr(err, "traceback", []) or []
                            errors.append(
                                ErrorDetail(
                                    type=err_type,
                                    message=message,
                                    traceback=tb,
                                )
                            )

            # Collect stderr messages as error details
            if cell_op.console:
                console_outputs = (
                    cell_op.console
                    if isinstance(cell_op.console, list)
                    else [cell_op.console]
                )
                for console in console_outputs:
                    if console.channel == CellChannel.STDERR:
                        errors.append(
                            ErrorDetail(
                                type="STDERR",
                                message=str(console.data),
                                traceback=[],
                            )
                        )

            if errors:
                summaries.append(
                    CellErrorsSummary(
                        cell_id=cell_id,
                        errors=errors,
                    )
                )

        # Sort by cell_id for stable output
        summaries.sort(key=lambda s: s.cell_id)
        return summaries
