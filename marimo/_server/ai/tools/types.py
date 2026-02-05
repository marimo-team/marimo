# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional, TypeVar

from marimo._config.config import CopilotMode

# Type aliases for tool system
FunctionArgs = dict[str, Any]
ValidationFunction = Callable[[FunctionArgs], Optional[tuple[bool, str]]]

ToolSource = Literal["mcp", "backend", "frontend"]


@dataclass
class ToolDefinition:
    """Tool definition compatible with ai-sdk-ui format."""

    name: str
    description: str
    parameters: dict[str, Any]
    source: ToolSource
    mode: list[CopilotMode]  # tools can be available in multiple modes

    def __str__(self) -> str:
        return f"Tool(name={self.name}, description={self.description})"


@dataclass
class ToolCallResult:
    """Represents the result of a tool invocation."""

    tool_name: str
    result: Any
    error: Optional[str] = None


T = TypeVar("T")
