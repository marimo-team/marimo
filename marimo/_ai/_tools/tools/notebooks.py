from dataclasses import dataclass, field
from typing import Optional

from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.types import (
    EmptyArgs,
    SuccessResult,
)
from marimo._server.model import ConnectionState
from marimo._server.models.home import MarimoFile
from marimo._server.sessions import SessionManager
from marimo._types.ids import SessionId
from marimo._utils.paths import pretty_path


@dataclass
class NotebookInfo:
    name: str
    path: str
    session_id: Optional[SessionId] = None
    initialization_id: Optional[str] = None


@dataclass
class SummaryInfo:
    total_notebooks: int
    total_sessions: int
    active_connections: int


@dataclass
class GetActiveNotebooksData:
    summary: SummaryInfo
    notebooks: list[NotebookInfo]


def _default_active_notebooks_data() -> GetActiveNotebooksData:
    return GetActiveNotebooksData(
        summary=SummaryInfo(
            total_notebooks=0, total_sessions=0, active_connections=0
        ),
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

    def handle(self, args: EmptyArgs) -> GetActiveNotebooksOutput:
        del args
        context = self.context
        session_manager = context.session_manager
        active_files = self._get_active_sessions_internal(session_manager)

        # Build notebooks list
        notebooks: list[NotebookInfo] = []
        for file_info in active_files:
            notebooks.append(
                NotebookInfo(
                    name=file_info.name,
                    path=file_info.path,
                    session_id=file_info.session_id,
                    initialization_id=file_info.initialization_id,
                )
            )

        # Build summary statistics
        summary: SummaryInfo = SummaryInfo(
            total_notebooks=len(active_files),
            total_sessions=len(session_manager.sessions),
            active_connections=session_manager.get_active_connection_count(),
        )

        # Build data object
        data = GetActiveNotebooksData(summary=summary, notebooks=notebooks)

        # Return a success result with summary statistics and notebook details
        return GetActiveNotebooksOutput(
            data=data,
            next_steps=[
                "Use the `get_lightweight_cell_map` tool to get the content of a notebook",
                "Use the `get_cell_runtime_data` tool to get the code, errors, and variables of a cell if you already have the cell id",
            ],
        )

    # helper methods

    def _get_active_sessions_internal(
        self, session_manager: SessionManager
    ) -> list[MarimoFile]:
        """
        Get active sessions from the app state.

        This replicates the logic from marimo/_server/api/endpoints/home.py
        """
        import os

        files: list[MarimoFile] = []
        for session_id, session in session_manager.sessions.items():
            state = session.connection_state()
            if (
                state == ConnectionState.OPEN
                or state == ConnectionState.ORPHANED
            ):
                filename = session.app_file_manager.filename
                basename = os.path.basename(filename) if filename else None
                files.append(
                    MarimoFile(
                        name=(basename or "new notebook"),
                        path=(
                            pretty_path(filename) if filename else session_id
                        ),
                        session_id=session_id,
                        initialization_id=session.initialization_id,
                    )
                )
        # Return most recent notebooks first (reverse chronological order)
        return files[::-1]
