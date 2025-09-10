from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Optional, Protocol, TypeVar

from pydantic import BaseModel, Field

from marimo._types.ids import SessionId

if TYPE_CHECKING:
    from collections.abc import Awaitable


# helper classes


# Use an Enum instead of Literal to avoid importing typing_extensions (banned)
# and to retain compatibility with Python 3.9/Pydantic during validation.
class StatusValue(str, Enum):
    success = "success"
    error = "error"
    warning = "warning"


class SuccessResult(BaseModel):
    status: StatusValue = StatusValue.success
    auth_required: bool = False
    next_steps: Optional[list[str]] = None
    action_url: Optional[str] = None
    message: Optional[str] = None
    meta: Optional[dict[str, Any]] = None


class EmptyArgs(BaseModel):
    pass


# base.py
ArgsT = TypeVar("ArgsT", bound=BaseModel)
OutT = TypeVar("OutT", bound=BaseModel)

ArgsP = TypeVar("ArgsP", bound=BaseModel, contravariant=True)
OutC = TypeVar("OutC", bound=BaseModel, covariant=True)


class GenericMcpHandler(Protocol[ArgsP, OutC]):
    """Tells mypy the async handler takes Args and returns Output, avoiding type errors."""

    def __call__(self, args: ArgsP, /) -> Awaitable[OutC]: ...


# cells.py
class SupportedCellType(str, Enum):
    CODE = "code"
    MARKDOWN = "markdown"
    SQL = "sql"


class GetLightweightCellMapArgs(BaseModel):
    session_id: str
    preview_lines: int = Field(default=3, ge=1, le=50)


class LightweightCellInfo(BaseModel):
    cell_id: str
    preview: str
    line_count: int
    cell_type: SupportedCellType


class GetLightweightCellMapOutput(SuccessResult):
    session_id: str
    notebook_name: str
    cells: list[LightweightCellInfo]
    total_cells: int
    preview_lines: int


class ErrorDetail(BaseModel):
    type: str
    message: str
    traceback: list[str]


class CellErrors(BaseModel):
    has_errors: bool
    error_details: Optional[list[ErrorDetail]]


# Mirrors marimo._ast.cell.RuntimeStateType; use Enum here for Pydantic/py39
# compatibility and to avoid Literal-based validation issues.
class RuntimeStateValue(str, Enum):
    idle = "idle"
    queued = "queued"
    running = "running"
    disabled_transitively = "disabled-transitively"


class CellRuntimeMetadata(BaseModel):
    runtime_state: Optional[RuntimeStateValue]
    execution_time: Optional[float]


class CellVariableValue(BaseModel):
    name: str
    # Cell variables can be arbitrary Python values (int, str, list, dict, ...),
    # so we keep this as Any to reflect actual runtime.
    value: Optional[Any] = None
    datatype: Optional[str] = None


CellVariables = dict[str, CellVariableValue]


class GetCellRuntimeDataData(BaseModel):
    session_id: str
    cell_id: str
    code: Optional[str]
    errors: Optional[CellErrors]
    metadata: Optional[CellRuntimeMetadata]
    variables: Optional[CellVariables]


class GetCellRuntimeDataArgs(BaseModel):
    session_id: str
    cell_id: str


class GetCellRuntimeDataOutput(SuccessResult):
    data: GetCellRuntimeDataData


# notebooks.py
class NotebookInfo(BaseModel):
    name: str
    path: str
    session_id: Optional[SessionId]
    initialization_id: Optional[str]


class SummaryInfo(BaseModel):
    total_notebooks: int
    total_sessions: int
    active_connections: int


class GetActiveNotebooksData(BaseModel):
    summary: SummaryInfo
    notebooks: list[NotebookInfo]


class GetActiveNotebooksOutput(SuccessResult):
    data: GetActiveNotebooksData
