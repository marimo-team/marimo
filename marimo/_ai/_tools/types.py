# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from marimo._types.ids import CellId_t, SessionId

# helper classes
StatusValue = Literal["success", "error", "warning"]


@dataclass
class SuccessResult:
    """Result returned by a successful AI tool call, with optional action URL and metadata."""

    status: StatusValue = "success"
    auth_required: bool = False
    next_steps: Optional[list[str]] = None
    action_url: Optional[str] = None
    message: Optional[str] = None
    meta: Optional[dict[str, Any]] = None


@dataclass
class EmptyArgs:
    """Placeholder argument class for AI tools that take no parameters."""

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
    """Metadata about a running marimo notebook session."""

    name: str
    path: str
    session_id: SessionId


@dataclass
class MarimoCellErrors:
    """Errors and stderr output collected from a single notebook cell."""

    cell_id: CellId_t
    errors: list[MarimoErrorDetail] = field(default_factory=list)
    stderr: list[str] = field(default_factory=list)


@dataclass
class MarimoErrorDetail:
    """Structured representation of a single error with its type, message, and traceback."""

    type: str
    message: str
    traceback: list[str]


@dataclass
class MarimoCellConsoleOutputs:
    """Captured stdout and stderr output from a notebook cell."""

    stdout: list[str] = field(default_factory=list)
    stderr: list[str] = field(default_factory=list)


@dataclass
class ListSessionsResult:
    """Result listing all currently running marimo notebook sessions."""

    sessions: list[MarimoNotebookInfo] = field(default_factory=list)


@dataclass
class CodeExecutionResult:
    """Result of executing code in a marimo notebook cell, including output and error information."""

    success: bool
    output: Optional[str] = None
    stdout: list[str] = field(default_factory=list)
    stderr: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    error: Optional[str] = None
