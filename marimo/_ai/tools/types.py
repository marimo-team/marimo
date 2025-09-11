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
