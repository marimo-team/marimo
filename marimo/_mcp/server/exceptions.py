# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ToolErrorDetails:
    """Structured representation of tool execution error details."""

    message: str
    code: str = "TOOL_ERROR"
    status: int = 400
    is_retryable: bool = False
    suggested_fix: Optional[str] = None
    meta: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the error details."""
        return {
            "message": self.message,
            "code": self.code,
            "status": self.status,
            "is_retryable": self.is_retryable,
            "suggested_fix": self.suggested_fix,
            "meta": self.meta or {},
        }


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
        # Create the structured error details using the dataclass
        self.details = ToolErrorDetails(
            message=message,
            code=code,
            status=status,
            is_retryable=is_retryable,
            suggested_fix=suggested_fix,
            meta=meta,
        )

        # Create a structured message that includes all error details
        structured_message = self._create_structured_message()
        super().__init__(structured_message)

    @property
    def original_message(self) -> str:
        """Access the original message through the details dataclass."""
        return self.details.message

    @property
    def code(self) -> str:
        """Access the error code through the details dataclass."""
        return self.details.code

    @property
    def status(self) -> int:
        """Access the status through the details dataclass."""
        return self.details.status

    @property
    def is_retryable(self) -> bool:
        """Access the retryable flag through the details dataclass."""
        return self.details.is_retryable

    @property
    def suggested_fix(self) -> Optional[str]:
        """Access the suggested fix through the details dataclass."""
        return self.details.suggested_fix

    @property
    def meta(self) -> dict[str, Any]:
        """Access the meta data through the details dataclass."""
        return self.details.meta or {}

    def _create_structured_message(self) -> str:
        """Create a message that includes all structured error information."""
        import json

        return json.dumps(self.details.to_dict(), separators=(",", ":"))

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the error details for testing."""
        return self.details.to_dict()
