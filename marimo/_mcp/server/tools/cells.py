from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from marimo._ast.cell import RuntimeStateType
from marimo._ast.models import CellData
from marimo._mcp.server.exceptions import ToolExecutionError
from marimo._mcp.server.responses import (
    SuccessResult,
)
from marimo._messaging.ops import VariableValue
from marimo._server.api.deps import AppStateBase
from marimo._types.ids import CellId_t, SessionId

if TYPE_CHECKING:
    from marimo._ast.cell import Cell
    from marimo._server.sessions import Session


class SupportedCellType(Enum):
    """Enum for core marimo cell types."""

    CODE = "code"
    MARKDOWN = "markdown"
    SQL = "sql"


@dataclass(kw_only=True)
class LightweightCellInfo:
    cell_id: str
    preview: str  # First X lines of code
    line_count: int
    cell_type: SupportedCellType


@dataclass(kw_only=True)
class GetLightweightCellMapData:
    session_id: str
    notebook_name: str
    cells: list[LightweightCellInfo]
    total_cells: int
    preview_lines: int  # How many lines were shown per cell


@dataclass(kw_only=True)
class GetLightweightCellMapResponse(SuccessResult):
    data: GetLightweightCellMapData


@dataclass(kw_only=True)
class ErrorDetail:
    type: str
    message: str
    traceback: list[str]


@dataclass(kw_only=True)
class CellErrors:
    has_errors: bool
    error_details: Optional[list[ErrorDetail]]


@dataclass(kw_only=True)
class CellRuntimeMetadata:
    runtime_state: Optional[RuntimeStateType]
    execution_time: Optional[float]


CellVariables = dict[str, VariableValue]


@dataclass(kw_only=True)
class GetCellRuntimeDataData:
    session_id: str
    cell_id: str
    code: Optional[str]
    errors: Optional[CellErrors]
    metadata: Optional[CellRuntimeMetadata]
    variables: Optional[CellVariables]


@dataclass(kw_only=True)
class GetCellRuntimeDataResponse(SuccessResult):
    data: GetCellRuntimeDataData


def register_cells_tools(mcp: FastMCP, app: Starlette) -> None:
    """Register cell-level management tools"""

    @mcp.tool()
    def get_lightweight_cell_map(
        session_id: str, preview_lines: int = 3
    ) -> GetLightweightCellMapResponse:
        """Get a lightweight map of cells showing the first few lines of each cell.

        This tool provides an overview of notebook structure for initial navigation,
        showing a preview of each cell's content without full code or outputs.

        Args:
            session_id: The session ID of the notebook from get_active_notebooks
            preview_lines: Number of lines to show per cell (default: 3)

        Returns:
            A success result containing lightweight cell previews and navigation info.
        """
        try:
            app_state = AppStateBase.from_app(app)

            # Access session manager and get the specific session
            session_manager = app_state.session_manager
            session_id_typed = SessionId(session_id)
            if session_id_typed not in session_manager.sessions:
                raise ToolExecutionError(
                    f"Session {session_id} not found",
                    code="SESSION_NOT_FOUND",
                    is_retryable=False,
                    suggested_fix="Use get_active_notebooks to find valid session IDs",
                )

            session = session_manager.sessions[session_id_typed]

            # Get cell manager from the session's app file manager
            cell_manager = session.app_file_manager.app.cell_manager
            notebook_filename = (
                session.app_file_manager.filename or "untitled_notebook.py"
            )

            # Build actual cell map from cell manager data
            cells: list[LightweightCellInfo] = []
            for cell_data in cell_manager.cell_data():
                code_lines = cell_data.code.split("\n")
                preview = "\n".join(code_lines[:preview_lines])

                # Determine cell type using actual marimo cell data when available
                cell_type = _determine_cell_type(
                    cell_data.code, cell_data.cell
                )

                cells.append(
                    LightweightCellInfo(
                        cell_id=cell_data.cell_id,
                        preview=preview,
                        line_count=len(code_lines),
                        cell_type=cell_type,
                    )
                )

            # Return a success result with lightweight cell map
            return GetLightweightCellMapResponse(
                data=GetLightweightCellMapData(
                    session_id=session_id,
                    notebook_name=notebook_filename,
                    cells=cells,
                    total_cells=len(cells),
                    preview_lines=preview_lines,
                ),
                next_steps=[
                    "Use cell_id to get full cell content or execute specific cells",
                    "Identify key sections based on cell types and previews",
                    "Focus on import cells first to understand dependencies",
                ],
                message="Refer to cells ordinally in the following format: @[cell:1]. Do _not_ use cell_id when discussing the with users.",
            )

        except Exception as e:
            # Return a structured error result
            raise ToolExecutionError(
                f"Failed to retrieve cell map for session {session_id}",
                code="CELL_MAP_ERROR",
                is_retryable=True,
                suggested_fix="Verify the session_id exists and the notebook is active. You can use the get_active_notebooks tool.",
                meta={
                    "session_id": session_id,
                    "preview_lines": preview_lines,
                },
            ) from e

    @mcp.tool()
    def get_cell_runtime_data(
        session_id: str, cell_id: str
    ) -> GetCellRuntimeDataResponse:
        """Get runtime data for a specific cell including code, errors, and variables.

        This tool provides detailed runtime information for a specific cell,
        including its source code, any execution errors, and the variables
        defined or modified in that cell.

        Args:
            session_id: The session ID of the notebook from get_active_notebooks
            cell_id: The specific cell ID to get runtime data for from get_lightweight_cell_map

        Returns:
            A success result containing cell runtime data including code, errors, and variables.
        """
        try:
            app_state = AppStateBase.from_app(app)

            # Access session manager and get the specific session
            session_manager = app_state.session_manager
            session_id_typed = SessionId(session_id)
            if session_id_typed not in session_manager.sessions:
                raise ToolExecutionError(
                    f"Session {session_id} not found",
                    code="SESSION_NOT_FOUND",
                    is_retryable=False,
                    suggested_fix="Use get_active_notebooks to find valid session IDs",
                )

            session = session_manager.sessions[session_id_typed]
            cell_manager = session.app_file_manager.app.cell_manager

            # Get cell data using CellManager's existing method
            cell_id_typed = CellId_t(cell_id)
            cell_data = cell_manager.get_cell_data(cell_id_typed)
            if cell_data is None:
                raise ToolExecutionError(
                    f"Cell {cell_id} not found in session {session_id}",
                    code="CELL_NOT_FOUND",
                    is_retryable=False,
                    suggested_fix="Use get_lightweight_cell_map to find valid cell IDs",
                )

            # Get cell code/source
            cell_code = cell_data.code

            # Get cell errors from session view with actual error details
            cell_errors = _get_cell_errors(session, cell_id_typed)

            # Get cell runtime metadata
            cell_metadata = _get_cell_metadata(session, cell_id_typed)

            # Get variable names and values defined by the cell
            cell_variables = _get_cell_variables(session, cell_data)

            return GetCellRuntimeDataResponse(
                data=GetCellRuntimeDataData(
                    session_id=session_id,
                    cell_id=cell_id,
                    code=cell_code,
                    errors=cell_errors,
                    metadata=cell_metadata,
                    variables=cell_variables,
                ),
                next_steps=[
                    "Review cell code for understanding the implementation",
                    "Check errors to identify any execution issues",
                    "Examine variables to understand cell outputs and state",
                ],
            )

        except ToolExecutionError:
            # Re-raise our specific tool errors (like CELL_NOT_FOUND, SESSION_NOT_FOUND)
            raise
        except Exception as e:
            # Only catch unexpected exceptions
            raise ToolExecutionError(
                f"Failed to retrieve runtime data for cell {cell_id} in session {session_id}",
                code="CELL_RUNTIME_ERROR",
                is_retryable=True,
                suggested_fix="Verify the session_id using get_active_notebooks and the cell_id using get_lightweight_cell_map.",
                meta={"session_id": session_id, "cell_id": cell_id},
            ) from e


# Utility functions
def is_markdown_cell(code: str) -> bool:
    """Check if a cell is a markdown cell."""
    if code.lstrip().startswith("mo.md("):
        return True
    return False


def _determine_cell_type(
    code: str, cell: Optional["Cell"] = None
) -> SupportedCellType:
    """Determine the type of cell based on marimo's compiled cell data.

    Uses the actual Language field from CellData.cell.language when available,
    falling back to code analysis for edge cases.
    Only returns types from Literal["code", "markdown", "sql"].
    """

    # If we have the compiled cell data, use marimo's official language detection
    if cell is not None:
        language = cell._cell.language
        if language == "sql":
            return SupportedCellType.SQL
        elif language == "python":
            # For Python cells, check if it's actually a markdown cell
            # by using marimo's official markdown detection
            if is_markdown_cell(code):
                return SupportedCellType.MARKDOWN
            return SupportedCellType.CODE

    # Default to code for all other cases
    return SupportedCellType.CODE


def _get_cell_errors(session: "Session", cell_id: CellId_t) -> CellErrors:
    """Get cell errors from session view with actual error details."""
    from marimo._messaging.cell_output import CellChannel

    # Get cell operation from session view
    session_view = session.session_view
    cell_op = session_view.cell_operations.get(cell_id)

    if cell_op is None:
        # No operations recorded for this cell
        return CellErrors(has_errors=False, error_details=None)

    # Check for actual error details in the output
    has_errors = False
    error_details = []
    if cell_op.output and cell_op.output.channel == CellChannel.MARIMO_ERROR:
        has_errors = True
        # Extract actual error objects
        errors = cell_op.output.data
        if isinstance(errors, list):
            for error in errors:
                if hasattr(error, "type") and hasattr(error, "describe"):
                    # Rich Error object
                    error_detail = ErrorDetail(
                        type=error.type,
                        message=error.describe(),
                        traceback=getattr(error, "traceback", []),
                    )
                    error_details.append(error_detail)
                elif isinstance(error, dict):
                    # Dict-based error
                    dict_error_detail = ErrorDetail(
                        type=error.get("type", "UnknownError"),
                        message=error.get("msg", str(error)),
                        traceback=error.get("traceback", []),
                    )
                    error_details.append(dict_error_detail)
                else:
                    # Fallback for other error types
                    fallback_error_detail = ErrorDetail(
                        type=type(error).__name__,
                        message=str(error),
                        traceback=[],
                    )
                    error_details.append(fallback_error_detail)

    # Check console outputs for STDERR (includes print statements to stderr, warnings, etc.)
    if cell_op.console:
        console_outputs = (
            cell_op.console
            if isinstance(cell_op.console, list)
            else [cell_op.console]
        )
        for console_output in console_outputs:
            if console_output.channel == CellChannel.STDERR:
                has_errors = True
                stderr_error_detail = ErrorDetail(
                    type="STDERR",
                    message=str(console_output.data),
                    traceback=[],
                )
                error_details.append(stderr_error_detail)

    return CellErrors(
        has_errors=has_errors,
        error_details=error_details if error_details else None,
    )


def _get_cell_metadata(
    session: "Session", cell_id: CellId_t
) -> CellRuntimeMetadata:
    """Get cell runtime metadata including status and execution info."""
    # Get basic runtime state from session view
    session_view = session.session_view
    cell_op = session_view.cell_operations.get(cell_id)

    runtime_state = None
    if cell_op and cell_op.status is not None:
        runtime_state = cell_op.status

    # Get execution time if available
    execution_time = session_view.last_execution_time.get(cell_id)

    return CellRuntimeMetadata(
        runtime_state=runtime_state, execution_time=execution_time
    )


def _get_cell_variables(
    session: "Session", cell_data: Optional[CellData]
) -> CellVariables:
    """Get variables defined by a specific cell and their values."""
    if not cell_data or not cell_data.cell:
        return {}

    # Get all current variables from session view
    session_view = session.session_view
    all_variables = session_view.variable_values

    # Get variables defined by this cell
    cell_defs = cell_data.cell._cell.defs

    # Filter to only variables defined by this cell
    cell_variables: CellVariables = {}
    for var_name in cell_defs:
        if var_name in all_variables:
            var_value = all_variables[var_name]
            cell_variables[var_name] = var_value

    return cell_variables
