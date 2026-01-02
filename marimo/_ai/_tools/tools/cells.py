# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from marimo._ai._tools.base import ToolBase
from marimo._ai._tools.types import (
    MarimoCellConsoleOutputs,
    MarimoErrorDetail,
    SuccessResult,
    ToolGuidelines,
)
from marimo._ai._tools.utils.exceptions import ToolExecutionError
from marimo._ast.models import CellData
from marimo._messaging.errors import Error
from marimo._messaging.notification import (
    CellNotification,
    VariableValue,
)
from marimo._types.ids import CellId_t, SessionId

if TYPE_CHECKING:
    from marimo._ast.models import CellData
    from marimo._session import Session


class SupportedCellType(str, Enum):
    CODE = "code"
    MARKDOWN = "markdown"
    SQL = "sql"


@dataclass
class GetLightweightCellMapArgs:
    session_id: SessionId
    preview_lines: int = 3  # random default value


@dataclass
class LightweightCellInfo:
    cell_id: str
    preview: str
    line_count: int
    cell_type: SupportedCellType


@dataclass
class GetLightweightCellMapOutput(SuccessResult):
    session_id: str = ""
    notebook_name: str = ""
    cells: list[LightweightCellInfo] = field(default_factory=list)
    total_cells: int = 0
    preview_lines: int = 3


@dataclass
class CellRuntimeMetadata:
    # String form of the runtime state (see marimo._ast.cell.RuntimeStateType);
    # keep as str for py39/Pydantic compatibility and to avoid Literal/Enum
    # validation issues in models.
    runtime_state: Optional[str] = None
    execution_time: Optional[float] = None


CellVariables = dict[str, VariableValue]


@dataclass
class GetCellRuntimeDataData:
    session_id: str
    cell_id: str
    code: Optional[str] = None
    errors: Optional[list[MarimoErrorDetail]] = None
    metadata: Optional[CellRuntimeMetadata] = None
    variables: Optional[CellVariables] = None


def _default_cell_runtime_data() -> GetCellRuntimeDataData:
    return GetCellRuntimeDataData(session_id="", cell_id="")


@dataclass
class GetCellRuntimeDataArgs:
    session_id: SessionId
    cell_id: CellId_t


@dataclass
class GetCellRuntimeDataOutput(SuccessResult):
    data: GetCellRuntimeDataData = field(
        default_factory=_default_cell_runtime_data
    )


@dataclass
class CellVisualOutput:
    """Visual from a cell execution."""

    visual_output: Optional[str] = None
    visual_mimetype: Optional[str] = None


@dataclass
class GetCellOutputArgs:
    session_id: SessionId
    cell_id: CellId_t


@dataclass
class GetCellOutputOutput(SuccessResult):
    visual_output: CellVisualOutput = field(default_factory=CellVisualOutput)
    console_outputs: MarimoCellConsoleOutputs = field(
        default_factory=MarimoCellConsoleOutputs
    )


class GetLightweightCellMap(
    ToolBase[GetLightweightCellMapArgs, GetLightweightCellMapOutput]
):
    """Get a lightweight map of cells showing the first few lines of each cell.

    This tool provides an overview of notebook structure for initial navigation,
    showing a preview of each cell's content without full code or outputs.

    Args:
        session_id: The session ID of the notebook from get_active_notebooks
        preview_lines: Number of lines to show per cell (default: 3)

    Returns:
        A success result containing lightweight cell previews and navigation info.
    """

    guidelines = ToolGuidelines(
        when_to_use=[
            "To get an overview of notebook structure and all cell IDs",
            "When navigating a notebook before making targeted changes",
        ],
        prerequisites=[
            "You must have a valid session id from an active notebook",
        ],
    )

    def handle(
        self, args: GetLightweightCellMapArgs
    ) -> GetLightweightCellMapOutput:
        session_id = args.session_id
        context = self.context
        session = context.get_session(session_id)
        cell_manager = session.app_file_manager.app.cell_manager
        notebook_filename = (
            session.app_file_manager.filename or "untitled_notebook.py"
        )

        # Validate preview_lines
        preview_lines = max(1, min(50, args.preview_lines))

        cells: list[LightweightCellInfo] = []
        for cell_data in cell_manager.cell_data():
            code_lines = cell_data.code.split("\n")
            preview = "\n".join(code_lines[:preview_lines])

            # Determine cell type using compiled cell info when available
            cell_type = self._get_cell_type(cell_data)

            # Add cell to cell map
            cells.append(
                LightweightCellInfo(
                    cell_id=cell_data.cell_id,
                    preview=preview,
                    line_count=len(code_lines),
                    cell_type=cell_type,
                )
            )

        return GetLightweightCellMapOutput(
            status="success",
            session_id=args.session_id,
            notebook_name=notebook_filename,
            cells=cells,
            total_cells=len(cells),
            preview_lines=preview_lines,
            next_steps=[
                "Use cell_id to get full cell content or execute specific cells",
                "Identify key sections based on cell types and previews",
                "Focus on import cells first to understand dependencies",
            ],
            message=(
                "Refer to cells ordinally in the following format: @[cell:1]. "
                "Do _not_ use cell_id when discussing with users."
            ),
        )

    # helper methods

    def _is_markdown_cell(self, code: str) -> bool:
        return code.lstrip().startswith("mo.md(")

    def _get_cell_type(self, cell_data: CellData) -> SupportedCellType:
        if cell_data.cell is None:
            # Fallback when compiled cell is unavailable
            return (
                SupportedCellType.MARKDOWN
                if self._is_markdown_cell(cell_data.code)
                else SupportedCellType.CODE
            )

        # Otherwise, use the compiled cell's language
        language = cell_data.cell._cell.language
        if language == "sql":
            return SupportedCellType.SQL
        elif language == "python":
            return (
                SupportedCellType.MARKDOWN
                if self._is_markdown_cell(cell_data.code)
                else SupportedCellType.CODE
            )
        else:
            return SupportedCellType.CODE


class GetCellRuntimeData(
    ToolBase[GetCellRuntimeDataArgs, GetCellRuntimeDataOutput]
):
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

    guidelines = ToolGuidelines(
        when_to_use=[
            "When inspecting a specific cell's code, errors, or variables",
            "After identifying a cell of interest from the cell map",
        ],
        prerequisites=[
            "You must have a valid session id from an active notebook",
            "You must have a valid cell id from an active notebook",
        ],
    )

    def handle(self, args: GetCellRuntimeDataArgs) -> GetCellRuntimeDataOutput:
        session_id = args.session_id
        cell_id = args.cell_id
        context = self.context
        session = context.get_session(session_id)

        # Get cell data using CellManager's existing method
        cell_data = self._get_cell_data(session, session_id, cell_id)

        # Get cell code/source
        cell_code = cell_data.code

        # Get cell errors from session view with actual error details
        cell_errors = context.get_cell_errors(session_id, cell_id)

        # Get cell runtime metadata
        cell_metadata = self._get_cell_metadata(session, cell_id)

        # Get variable names and values defined by the cell
        cell_variables = self._get_cell_variables(session, cell_data)

        return GetCellRuntimeDataOutput(
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

    # helper methods

    def _get_cell_data(
        self, session: Session, session_id: SessionId, cell_id: CellId_t
    ) -> CellData:
        cell_manager = session.app_file_manager.app.cell_manager
        cell_data = cell_manager.get_cell_data(cell_id)
        if cell_data is None:
            raise ToolExecutionError(
                f"Cell {cell_id} not found in session {session_id}",
                code="CELL_NOT_FOUND",
                is_retryable=False,
                suggested_fix="Use get_lightweight_cell_map to find valid cell IDs",
            )
        return cell_data

    def _get_cell_metadata(
        self, session: Session, cell_id: CellId_t
    ) -> CellRuntimeMetadata:
        """Get cell runtime metadata including status and execution info."""
        # Get basic runtime state from session view
        session_view = session.session_view
        cell_notif = session_view.cell_notifications.get(cell_id)

        runtime_state = None
        if cell_notif and cell_notif.status is not None:
            runtime_state = cell_notif.status

        # Get execution time if available
        execution_time = session_view.last_execution_time.get(cell_id)

        return CellRuntimeMetadata(
            runtime_state=runtime_state, execution_time=execution_time
        )

    def _get_cell_variables(
        self, session: Session, cell_data: Optional[CellData]
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


class GetCellOutputs(ToolBase[GetCellOutputArgs, GetCellOutputOutput]):
    """Get cell execution output including visual display and console streams.

    Args:
        session_id: The session ID of the notebook from get_active_notebooks
        cell_id: The specific cell ID from get_lightweight_cell_map

    Returns:
        Visual output (HTML, charts, tables, etc.) with mimetype and console streams (stdout/stderr).
    """

    guidelines = ToolGuidelines(
        when_to_use=[
            "When you need to see what a cell displayed or printed to the user",
            "To review charts, visualizations, markdown, HTML, or console output from a cell",
        ],
        prerequisites=[
            "You must have a valid session id from an active notebook",
            "You must have a valid cell id from an active notebook",
        ],
    )

    def handle(self, args: GetCellOutputArgs) -> GetCellOutputOutput:
        context = self.context
        session = context.get_session(args.session_id)
        session_view = session.session_view
        cell_id = args.cell_id
        cell_notif = session_view.cell_notifications.get(cell_id)

        if cell_notif is None:
            raise ToolExecutionError(
                f"Cell {cell_id} not found in session {args.session_id}",
                code="CELL_NOT_FOUND",
                is_retryable=False,
                suggested_fix="Use get_lightweight_cell_map to find valid cell IDs",
            )

        visual_output, visual_mimetype = self._get_visual_output(cell_notif)
        console_outputs = context.get_cell_console_outputs(cell_notif)

        return GetCellOutputOutput(
            visual_output=CellVisualOutput(
                visual_output=visual_output,
                visual_mimetype=visual_mimetype,
            ),
            console_outputs=console_outputs,
            next_steps=[
                "Review visual_output to see what was displayed to the user",
                "Check stdout/stderr for print statements and warnings",
            ],
        )

    def _get_visual_output(
        self, cell_notif: CellNotification
    ) -> tuple[Optional[str], Optional[str]]:
        visual_output = None
        visual_mimetype = None
        if cell_notif.output:
            data = cell_notif.output.data
            visual_output = self._get_str_output_data(data)
            visual_mimetype = cell_notif.output.mimetype
        return visual_output, visual_mimetype

    def _get_str_output_data(
        self, data: str | list[Error] | dict[str, Any]
    ) -> str:
        if isinstance(data, str):
            return data
        else:
            return str(data)
