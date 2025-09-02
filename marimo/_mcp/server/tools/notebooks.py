from typing import Optional, TypedDict

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from marimo._mcp.server.exceptions import ToolExecutionError
from marimo._mcp.server.responses import (
    SuccessResult,
    make_tool_success_result,
)
from marimo._server.api.deps import AppStateBase
from marimo._server.model import ConnectionState
from marimo._server.models.home import MarimoFile
from marimo._types.ids import SessionId
from marimo._utils.paths import pretty_path


class NotebookInfo(TypedDict):
    name: str
    path: str
    session_id: Optional[SessionId]
    initialization_id: Optional[str]


class SummaryInfo(TypedDict):
    total_notebooks: int
    total_sessions: int
    active_connections: int


class GetActiveNotebooksResponse(TypedDict):
    summary: SummaryInfo
    notebooks: list[NotebookInfo]


def register_notebooks_tools(mcp: FastMCP, app: Starlette) -> None:
    """Register notebook-level management tools"""

    @mcp.tool()
    def get_active_notebooks() -> SuccessResult[GetActiveNotebooksResponse]:
        """List currently active marimo notebooks and a summary block.

        Returns:
            A success result containing summary statistics and notebook details.
        """
        try:
            app_state = AppStateBase.from_app(app)
            active_files = _get_active_sessions_internal(app_state)

            # Build notebooks list
            notebooks: list[NotebookInfo] = []
            for file_info in active_files:
                notebooks.append(
                    {
                        "name": file_info.name,
                        "path": file_info.path,
                        "session_id": file_info.session_id,
                        "initialization_id": file_info.initialization_id,
                    }
                )

            # Build summary statistics
            session_manager = app_state.session_manager
            summary: SummaryInfo = {
                "total_notebooks": len(active_files),
                "total_sessions": len(session_manager.sessions),
                "active_connections": session_manager.get_active_connection_count(),
            }

            # Return a success result with summary statistics and notebook details
            return make_tool_success_result(
                data={"summary": summary, "notebooks": notebooks},
                next_steps=[
                    "Use the `get_lightweight_cell_map` tool to get the content of a notebook"
                ],
            )

        except Exception as e:
            # Return a structured error result
            raise ToolExecutionError(
                "Failed to retrieve active notebooks",
                code="NOTEBOOK_FETCH_ERROR",
                is_retryable=True,
                suggested_fix="Tell the user to check if marimo server is running and accessible. Suggest restarting the server if they havent already tried that.",
            ) from e


# Utility functions


def _get_active_sessions_internal(app_state: AppStateBase) -> list[MarimoFile]:
    """
    Get active sessions from the app state.

    This replicates the logic from marimo/_server/api/endpoints/home.py
    """
    import os

    files: list[MarimoFile] = []
    for session_id, session in app_state.session_manager.sessions.items():
        state = session.connection_state()
        if state == ConnectionState.OPEN or state == ConnectionState.ORPHANED:
            filename = session.app_file_manager.filename
            basename = os.path.basename(filename) if filename else None
            files.append(
                MarimoFile(
                    name=(basename or "new notebook"),
                    path=(pretty_path(filename) if filename else session_id),
                    session_id=session_id,
                    initialization_id=session.initialization_id,
                )
            )
    # Return most recent notebooks first (reverse chronological order)
    return files[::-1]
