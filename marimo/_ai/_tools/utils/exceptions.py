# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass
class ToolExecutionError(Exception):
    """Raise this from a tool to signal a descriptive, structured failure."""

    message: str
    code: str = "TOOL_ERROR"
    status: int = 400
    is_retryable: bool = False
    suggested_fix: Optional[str] = None
    meta: Optional[dict[str, Any]] = None

    def __post_init__(self) -> None:
        # Initialize base Exception with the structured JSON message
        # Necessary since some MCP client (e.g. Cursor) only logs the original message
        super().__init__(self._create_structured_message())

    @property
    def original_message(self) -> str:
        return self.message

    def _create_structured_message(self) -> str:
        """Create a message that includes all structured error information."""
        import json

        payload = asdict(self)
        payload["meta"] = payload.get("meta", {})
        return json.dumps(payload, separators=(",", ":"))

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation for testing."""
        payload = asdict(self)
        payload["meta"] = payload.get("meta", {})
        return payload
