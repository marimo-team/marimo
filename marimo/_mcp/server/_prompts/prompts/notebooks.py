# Copyright 2024 Marimo. All rights reserved.
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

        session_manager = self.context.session_manager

        # Get all active sessions
        sessions = session_manager.sessions

        if not sessions:
            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text="No active marimo notebook sessions found.",
                    ),
                )
            ]

        # Create a message for each session
        messages: list[PromptMessage] = []
        for session_id, session in sessions.items():
            # Get file path if available
            file_path = None
            if (
                hasattr(session, "app_file_manager")
                and session.app_file_manager
            ):
                file_path = session.app_file_manager.filename

            # Create actionable message for this session
            if file_path:
                message = (
                    f"Notebook session ID: {session_id}\n"
                    f"Notebook file path: {file_path}\n\n"
                    f"Use this session_id when calling MCP tools that require it. "
                    f"You can also edit the notebook directly by modifying the file at the path above."
                )
            else:
                message = (
                    f"Notebook session ID: {session_id}\n\n"
                    f"Use this session_id when calling MCP tools that require it."
                )

            messages.append(
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=message,
                    ),
                )
            )

        return messages
