# Add lifespan support for startup/shutdown with strong typing
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse

from marimo._ast.cell import CellOutput
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.ops import UpdateCellIdsRequest
from marimo._runtime.requests import DeleteCellRequest, ExecuteMultipleRequest
from marimo._server.file_router import MarimoFileKey
from marimo._server.sessions import (
    Session,
    SessionManager,  # Replace with your actual DB type
)
from marimo._types.ids import CellId_t, SessionId

if TYPE_CHECKING:
    from fastmcp import FastMCP


@dataclass
class AppContext:
    pass


def create_mcp_server(session_manager: SessionManager) -> FastMCP[AppContext]:
    from fastmcp import FastMCP

    # @asynccontextmanager
    # async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    #     """Manage application lifecycle with type-safe context"""
    #     try:
    #         yield AppContext()
    #     finally:
    #         pass

    # Pass lifespan to server
    mcp: FastMCP[AppContext] = FastMCP(
        name="marimo",
        instructions="""
        You are a helpful assistant that can edit and interact with marimo notebooks.
        """,
        debug=True,
        # lifespan=app_lifespan,
        # sse_path="/sse",
        # message_path="/messages",
    )

    @mcp.resource("notebooks://")
    def get_open_notebooks() -> str:
        """List all notebooks"""
        sessions = list(session_manager.sessions.values())
        return "\n".join(
            [
                Path(session.app_file_manager.filename).name
                for session in sessions
                if session.app_file_manager.filename is not None
            ]
        )

    @mcp.resource("cell://{filename}/codes")
    def get_codes(filename: str) -> str:
        """
        Get all the code in a marimo notebook

        Args:
            filename: The name of the marimo notebook to get the code for

        Returns:
            A string containing all the code in the marimo notebook. The header
            of each cell is prepended with `# %% {cell_id}`.
        """
        session = _find_session_by_filename(session_manager, filename)
        if session is None:
            return "Session not found"

        cell_ids = _get_cell_ids(session)

        codes: dict[str, str] = {}
        for cell_id in cell_ids:
            codes[cell_id] = session.session_view.last_executed_code[cell_id]

        return "\n".join(
            [f"# %% {cell_id}\n{code}" for cell_id, code in codes.items()]
        )

    @mcp.resource("cell://{filename}/errors")
    def get_errors(filename: str) -> str:
        """Get the errors of a marimo notebook"""
        session = _find_session_by_filename(session_manager, filename)
        if session is None:
            return "Session not found"
        cell_ids = _get_cell_ids(session)
        outputs = session.session_view.get_cell_outputs(cell_ids)
        console_outputs = session.session_view.get_cell_console_outputs(
            cell_ids
        )
        response = ""
        for cell_id, output in outputs.items():
            if (
                output.mimetype == "application/vnd.marimo+error"
                or output.mimetype == "application/vnd.marimo+traceback"
            ):
                response += f"Cell {cell_id} error: {str(output.data)}\n"
            elif (
                console_outputs[cell_id]
                and len(console_outputs[cell_id]) > 0
                and any(
                    output.channel == CellChannel.STDERR
                    for output in console_outputs[cell_id]
                )
            ):
                for output in console_outputs[cell_id]:
                    if output.channel == CellChannel.STDERR:
                        response += (
                            f"Cell {cell_id} error: {str(output.data)}\n"
                        )

        if not response:
            return "No errors found"

        return response

    @mcp.resource("cell://{filename}/output/{cell_id}")
    def get_cell_output(filename: str, cell_id: str) -> str:
        """Get the output of a cell"""
        session = _find_session_by_filename(session_manager, filename)
        if session is None:
            return "Session not found"
        c_id = CellId_t(cell_id)
        outputs = session.session_view.get_cell_outputs([c_id])
        console_outputs = session.session_view.get_cell_console_outputs([c_id])
        response = ""
        if c_id in outputs:
            response += f"Output:\n{str(outputs[c_id].data)}\n\n"
        if c_id in console_outputs:
            for output in console_outputs[c_id]:
                response += (
                    f"[{output.channel.value} Console]: {str(output.data)}\n\n"
                )
        return response.strip()

    @mcp.resource("cell://{filename}/status")
    def get_cell_status(filename: str) -> str:
        """Get the status of the notebook (running, idle, errored)"""
        session = _find_session_by_filename(session_manager, filename)
        if session is None:
            return "Session not found"
        cell_ids = _get_cell_ids(session)
        if len(cell_ids) == 0:
            return "No cells found"
        # "idle", "queued", "running", "disabled-transitively"
        statuses = [
            session.session_view.cell_operations[cell_id].status
            for cell_id in cell_ids
        ]
        if any(status == "running" for status in statuses):
            return "running"
        if any(status == "queued" for status in statuses):
            return "queued"
        outputs = session.session_view.get_cell_outputs(cell_ids)
        if any(
            output.mimetype == "application/vnd.marimo+error"
            or output.mimetype == "application/vnd.marimo+traceback"
            for output in outputs.values()
        ):
            return "errored"
        return "idle"

    # ExecuteMultipleRequest,
    # ExecuteScratchpadRequest,
    # ExecuteStaleRequest,
    # CreationRequest,
    # DeleteCellRequest,
    # FunctionCallRequest,
    # RenameRequest,
    # SetCellConfigRequest,
    # SetUserConfigRequest,
    # SetUIElementValueRequest,
    # StopRequest,
    # InstallMissingPackagesRequest,
    # PreviewDatasetColumnRequest,
    # PreviewSQLTableRequest,
    # PreviewSQLTableListRequest,

    @mcp.tool()
    def edit_and_run_cell(filename: str, cell_id: str, code: str) -> str:
        """Run all the code in a marimo notebook"""
        session = _find_session_by_filename(session_manager, filename)
        if session is None:
            return "Session not found"
        session.put_control_request(
            ExecuteMultipleRequest(
                cell_ids=[CellId_t(cell_id)],
                codes=[code],
            ),
            from_consumer_id=None,
        )

        return "Cell added and run"

    @mcp.tool()
    def edit_and_run_multiple_cells(
        filename: str,
        cell_ids: list[str],
        codes: list[str],
    ) -> str:
        """Edit multiple cells in a marimo notebook and run them"""
        session = _find_session_by_filename(session_manager, filename)
        if session is None:
            return "Session not found"
        session.put_control_request(
            ExecuteMultipleRequest(
                cell_ids=[CellId_t(cell_id) for cell_id in cell_ids],
                codes=codes,
            ),
            from_consumer_id=None,
        )
        return f"Cells {cell_ids} added and run"

    @mcp.tool()
    def add_cell(filename: str, code: str) -> str:
        """Add a cell to a marimo notebook"""
        session = _find_session_by_filename(session_manager, filename)
        if session is None:
            return "Session not found"

        # Generate a random cell ID
        import random
        import string

        # Create a random 4-letter ID
        alphabet = string.ascii_lowercase + string.ascii_uppercase
        cell_id = "".join(random.choice(alphabet) for _ in range(4))

        cell_ids = _get_cell_ids(session)
        session.write_operation(
            UpdateCellIdsRequest(cell_ids=cell_ids + [CellId_t(cell_id)]),
            from_consumer_id=None,
        )
        session.put_control_request(
            ExecuteMultipleRequest(
                cell_ids=[CellId_t(cell_id)],
                codes=[code],
            ),
            from_consumer_id=None,
        )

        return f"Cell {cell_id} added and run"

    @mcp.tool()
    def delete_cell(filename: str, cell_id: str) -> str:
        """Delete a cell from a marimo notebook"""
        session = _find_session_by_filename(session_manager, filename)
        if session is None:
            return "Session not found"
        session.put_control_request(
            DeleteCellRequest(cell_id=CellId_t(cell_id)),
            from_consumer_id=None,
        )
        return f"Cell {cell_id} deleted"

    @mcp.tool()
    def list_sessions() -> str:
        """List all sessions, outputting their file paths"""
        sessions = list(session_manager.sessions.values())
        return "\n".join(
            [
                Path(session.app_file_manager.filename).name
                for session in sessions
                if session.app_file_manager.filename is not None
            ]
        )

    @mcp.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy"})

    return mcp


# def _get_output(session: Session) -> str:
#     """Get the output of a session"""
#     return session.app_file_manager.filename


def _find_session_by_filename(
    session_manager: SessionManager, filename: str
) -> Optional[Session]:
    """
    Find a session by file name

    This doesn't work with multiple files with the same name,
    but we can deal with that later.
    """
    for session in session_manager.sessions.values():
        if session.app_file_manager.filename is None:
            continue
        fname = session.app_file_manager.filename
        if Path(fname).name == filename or fname == filename:
            return session
    print("Session not found")
    print(f"Given filename: {filename}")
    print("All sessions:")
    for session in session_manager.sessions.values():
        print(session.app_file_manager.filename)
    return None


def _get_cell_ids(session: Session) -> list[CellId_t]:
    """Get the cell IDs of a session"""

    if session.session_view.cell_ids:
        cell_ids = list(session.session_view.cell_ids.cell_ids)
    else:
        cell_ids = list(session.app_file_manager.app.cell_manager.cell_ids())

    return cell_ids
