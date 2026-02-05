# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field

from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.types import (
    EmptyArgs,
    MarimoNotebookInfo,
    SuccessResult,
    ToolGuidelines,
)


@dataclass
class SummaryInfo:
    total_notebooks: int
    active_connections: int


@dataclass
class GetActiveNotebooksData:
    summary: SummaryInfo
    notebooks: list[MarimoNotebookInfo]


def _default_active_notebooks_data() -> GetActiveNotebooksData:
    return GetActiveNotebooksData(
        summary=SummaryInfo(total_notebooks=0, active_connections=0),
        notebooks=[],
    )


@dataclass
class GetActiveNotebooksOutput(SuccessResult):
    data: GetActiveNotebooksData = field(
        default_factory=_default_active_notebooks_data
    )


class GetActiveNotebooks(ToolBase[EmptyArgs, GetActiveNotebooksOutput]):
    """List currently active marimo notebooks and a summary block.

    Returns:
        A success result containing summary statistics and notebook details.
    """

    guidelines = ToolGuidelines(
        when_to_use=[
            "At the start of marimo notebook interactions to get session IDs",
            "When receiving session-related errors",
        ],
        additional_info="Use the file paths returned by this tool to directly edit a notebook.",
    )

    def handle(self, args: EmptyArgs) -> GetActiveNotebooksOutput:
        del args
        context = self.context
        session_manager = context.session_manager
        notebooks = context.get_active_sessions_internal()

        summary: SummaryInfo = SummaryInfo(
            total_notebooks=len(notebooks),
            active_connections=session_manager.get_active_connection_count(),
        )

        data = GetActiveNotebooksData(summary=summary, notebooks=notebooks)

        return GetActiveNotebooksOutput(
            data=data,
            next_steps=[
                "Use the `get_lightweight_cell_map` tool to get the content of a notebook",
                "Use the `get_notebook_errors` tool to help debug errors in the notebook",
            ],
        )
