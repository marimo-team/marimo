# Copyright 2026 Marimo. All rights reserved.
"""MCP Prompts for notebook information."""

from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._mcp.server._prompts.base import PromptBase

if TYPE_CHECKING:
    from mcp.types import PromptMessage


class ActiveNotebooks(PromptBase):
    """Get current active notebooks and their session IDs and file paths."""

    def handle(self) -> list[PromptMessage]:
        """Generate prompt messages for all active notebook sessions.

        Returns:
            List of PromptMessage objects, one per active session.
        """
        from mcp.types import PromptMessage, TextContent

        context = self.context
        notebooks = context.get_active_sessions_internal()

        if len(notebooks) == 0:
            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text="No active marimo notebook sessions found.",
                    ),
                )
            ]

        session_messages: list[PromptMessage] = []
        for active_file in notebooks:
            session_message = (
                f"Notebook session ID: {active_file.session_id}\n"
                f"Notebook file path: {active_file.path}\n\n"
            )

            session_messages.append(
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=session_message,
                    ),
                )
            )

        action_message = (
            f"Use {'this session_id' if len(notebooks) == 1 else 'these session_ids'} when calling marimo MCP tools that require it."
            f"You can also edit {'this notebook' if len(notebooks) == 1 else 'these notebooks'} directly by modifying the files at the paths above."
        )

        session_messages.append(
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=action_message,
                ),
            )
        )

        return session_messages
