# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field

from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.types import (
    MarimoCellErrors,
    SuccessResult,
    ToolGuidelines,
)
from marimo._types.ids import SessionId


@dataclass
class GetNotebookErrorsArgs:
    session_id: SessionId


@dataclass
class GetNotebookErrorsOutput(SuccessResult):
    has_errors: bool = False
    total_errors: int = 0
    total_cells_with_errors: int = 0
    cells: list[MarimoCellErrors] = field(default_factory=list)


class GetNotebookErrors(
    ToolBase[GetNotebookErrorsArgs, GetNotebookErrorsOutput]
):
    """
    Get all errors in the current notebook session, organized by cell.

    Args:
        session_id: The session ID of the notebook.

    Returns:
        A success result containing notebook errors organized by cell.
    """

    guidelines = ToolGuidelines(
        when_to_use=[
            "When the user reports errors or issues in their notebook",
            "Before debugging or fixing broken cells",
        ],
        prerequisites=[
            "You must have a valid session id from an active notebook",
        ],
    )

    def handle(self, args: GetNotebookErrorsArgs) -> GetNotebookErrorsOutput:
        context = self.context
        session_id = args.session_id
        notebook_errors = context.get_notebook_errors(
            session_id, include_stderr=True
        )

        total_errors = sum(len(c.errors) for c in notebook_errors)
        total_cells_with_errors = len(notebook_errors)
        has_errors = total_errors > 0

        return GetNotebookErrorsOutput(
            has_errors=has_errors,
            total_errors=total_errors,
            total_cells_with_errors=total_cells_with_errors,
            cells=notebook_errors,
            next_steps=(
                [
                    "Use get_cell_runtime_data to inspect the impacted cells to fix syntax/runtime issues",
                    "Re-run the notebook after addressing the errors",
                ]
                if has_errors
                else ["No errors detected"]
            ),
        )
