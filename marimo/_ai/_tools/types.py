# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from marimo._types.ids import CellId_t, SessionId

# helper classes
StatusValue = Literal["success", "error", "warning"]


@dataclass
class SuccessResult:
    status: StatusValue = "success"
    auth_required: bool = False
    next_steps: Optional[list[str]] = None
    action_url: Optional[str] = None
    message: Optional[str] = None
    meta: Optional[dict[str, Any]] = None


@dataclass
class EmptyArgs:
    pass


@dataclass
class ToolGuidelines:
    """Structured guidance for AI assistants on when and how to use a tool."""

    when_to_use: Optional[list[str]] = None
    avoid_if: Optional[list[str]] = None
    prerequisites: Optional[list[str]] = None
    side_effects: Optional[list[str]] = None
    additional_info: Optional[str] = None


@dataclass
class MarimoNotebookInfo:
    name: str
    path: str
    session_id: SessionId


@dataclass
class MarimoCellErrors:
    cell_id: CellId_t
    errors: list[MarimoErrorDetail] = field(default_factory=list)
    stderr: list[str] = field(default_factory=list)


@dataclass
class MarimoErrorDetail:
    type: str
    message: str
    traceback: list[str]


@dataclass
class MarimoCellConsoleOutputs:
    stdout: list[str] = field(default_factory=list)
    stderr: list[str] = field(default_factory=list)
