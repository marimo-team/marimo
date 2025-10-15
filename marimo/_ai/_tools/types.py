# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

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
