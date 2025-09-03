# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import Any, Optional, TypedDict


class ToolExecutionErrorDict(TypedDict):
    message: str
    code: str
    status: int
    is_retryable: bool
    suggested_fix: Optional[str]
    meta: Optional[dict[str, Any]]


class ToolExecutionError(Exception):
    """Raise this from a tool to signal a descriptive, structured failure."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "TOOL_ERROR",
        status: int = 400,
        is_retryable: bool = False,
        suggested_fix: Optional[str] = None,
        meta: Optional[dict[str, Any]] = None,
    ):
        self.original_message = message
        self.code = code
        self.status = status
        self.is_retryable = is_retryable
        self.suggested_fix = suggested_fix
        self.meta = meta or {}

        # Create a structured message that includes all error details
        structured_message = self._create_structured_message()
        super().__init__(structured_message)

    def _create_structured_message(self) -> str:
        """Create a message that includes all structured error information."""
        error_dict: ToolExecutionErrorDict = {
            "message": self.original_message,
            "code": self.code,
            "status": self.status,
            "is_retryable": self.is_retryable,
            "suggested_fix": self.suggested_fix,
            "meta": self.meta,
        }
        return json.dumps(error_dict)

    def to_dict(self) -> ToolExecutionErrorDict:
        """Return a dictionary representation of the error details for testing."""
        error_dict: ToolExecutionErrorDict = {
            "code": self.code,
            "message": self.original_message,
            "status": self.status,
            "is_retryable": self.is_retryable,
            "suggested_fix": self.suggested_fix,
            "meta": self.meta,
        }
        return error_dict
