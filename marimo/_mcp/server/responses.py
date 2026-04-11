# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(kw_only=True)
class SuccessResult:
    status: Literal["success", "error", "warning"] = "success"
    auth_required: bool = False
    next_steps: list[str] | None = None
    action_url: str | None = None
    message: str | None = None
    meta: dict[str, Any] | None = None
