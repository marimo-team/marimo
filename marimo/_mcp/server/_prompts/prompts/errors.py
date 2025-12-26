# Copyright 2026 Marimo. All rights reserved.
"""MCP Prompts for notebook error information."""

from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._mcp.server._prompts.base import PromptBase

if TYPE_CHECKING:
    from mcp.types import PromptMessage


class ErrorsSummary(PromptBase):
    """Get error summaries for all active notebooks."""

    def handle(self) -> list[PromptMessage]:
        """Generate prompt messages summarizing errors in active notebooks.

        Returns:
            List of PromptMessage objects, one per notebook with errors.
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

        error_messages: list[PromptMessage] = []

        for notebook in notebooks:
            session_id = notebook.session_id
            notebook_errors = context.get_notebook_errors(
                session_id, include_stderr=False
            )

            if len(notebook_errors) == 0:
                continue

            error_lines = [
                f"Notebook: {notebook.name} (session: {notebook.session_id})",
                f"Path: {notebook.path}",
                f"Cells with errors: {len(notebook_errors)}",
                f"Total errors: {sum(len(cell_errors.errors) for cell_errors in notebook_errors)}",
            ]

            for cell_errors in notebook_errors:
                error_lines.append(f"**Cell {cell_errors.cell_id}**:")
                all_cell_errors = [
                    f"    • {error.type} - {error.message}"
                    for error in cell_errors.errors
                ]
                error_lines.extend(all_cell_errors)

            error_messages.append(
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text="\n".join(error_lines),
                    ),
                )
            )

        if len(error_messages) == 0:
            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text="No errors found in any active notebooks.",
                    ),
                )
            ]

        return error_messages
