# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from marimo._types.ids import CellId_t, SessionId

# helper classes
StatusValue = Literal["success", "error", "warning"]


@dataclass
class SuccessResult:
    status: StatusValue = "success"
    auth_required: bool = False
    next_steps: list[str] | None = None
    action_url: str | None = None
    message: str | None = None
    meta: dict[str, Any] | None = None


@dataclass
class EmptyArgs:
    pass


@dataclass
class ToolGuidelines:
    """Structured guidance for AI assistants on when and how to use a tool."""

    when_to_use: list[str] | None = None
    avoid_if: list[str] | None = None
    prerequisites: list[str] | None = None
    side_effects: list[str] | None = None
    additional_info: str | None = None


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


@dataclass
class ListSessionsResult:
    sessions: list[MarimoNotebookInfo] = field(default_factory=list)


@dataclass
class CodeExecutionResult:
    success: bool
    output: str | None = None
    stdout: list[str] = field(default_factory=list)
    stderr: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    error: str | None = None
