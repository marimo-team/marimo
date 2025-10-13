# Copyright 2024 Marimo. All rights reserved.
"""Base class for MCP prompts."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from mcp.types import PromptMessage

    from marimo._ai._tools.base import ToolContext


class PromptBase(ABC):
    """Base class for MCP prompts.

    Subclasses should:
    - Set description via class docstring (or override description attribute)
    - Implement get_messages() to return list[PromptMessage]
    """

    name: str = ""
    description: str = ""
    context: ToolContext

    def __init__(self, context: ToolContext) -> None:
        self.context = context

        # Infer name from class name (e.g., ActiveNotebooksPrompt -> active_notebooks_prompt)
        if self.name == "":
            self.name = self._to_snake_case(self.__class__.__name__)

        # Get description from class docstring
        if self.description == "":
            self.description = (self.__class__.__doc__ or "").strip()

    @abstractmethod
    def handle(self) -> list[PromptMessage]:
        """Generate prompt messages."""
        ...

    def as_mcp_prompt_fn(self) -> Callable[[], list[PromptMessage]]:
        """Return a callable suitable for mcp.prompt() registration."""
        from mcp.types import PromptMessage, TextContent

        def handler() -> list[PromptMessage]:
            try:
                return self.handle()
            except Exception as e:
                # Return error as a prompt message instead of raising
                error_message = (
                    f"Error generating prompt '{self.name}': {str(e)}\n\n"
                    f"Please try again or contact support if the issue persists."
                )
                return [
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=error_message,
                        ),
                    )
                ]

        # Set metadata for MCP registration
        handler.__name__ = self.name
        handler.__doc__ = self.description
        handler.__annotations__ = {"return": list[PromptMessage]}

        return handler

    def _to_snake_case(self, name: str) -> str:
        """Convert PascalCase class name to snake_case.

        Examples:
            ActiveNotebooksPrompt -> active_notebooks_prompt
            ActiveNotebooks -> active_notebooks
        """
        s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
        s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
        return s2.replace("-", "_").lower()
