# Copyright 2025 Marimo. All rights reserved.

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Generic, Literal, Optional, TypeVar

from marimo._config.config import CopilotMode

# Type aliases for tool system
FunctionArgs = dict[str, Any]
ValidationFunction = Callable[[FunctionArgs], Optional[tuple[bool, str]]]

ToolSource = Literal["mcp", "backend", "frontend"]


@dataclass
class Tool:
    """Tool definition compatible with ai-sdk-ui format."""

    name: str
    description: str
    parameters: dict[str, Any]
    source: ToolSource
    mode: list[CopilotMode]  # tools can be available in multiple modes

    def __str__(self) -> str:
        return f"Tool(name={self.name}, description={self.description})"


@dataclass
class ToolResult:
    """Represents the result of a tool invocation."""

    tool_name: str
    result: Any
    error: Optional[str] = None


T = TypeVar("T")


class BackendTool(ABC, Generic[T]):
    """Base class for all backend tools."""

    @property
    @abstractmethod
    def tool(self) -> Tool:
        """The tool definition."""

    @abstractmethod
    def handler(self, arguments: T) -> dict[str, Any]:
        """The handler function for the tool."""

    @abstractmethod
    def validator(self, arguments: T) -> Optional[tuple[bool, str]]:
        """The validator function for the tool parameters.
        Strongly recommended to return a tuple of (is_valid, error_message).

        If None is returned, the tool will be validated against the parameters schema.
        """
        del arguments
        return None
