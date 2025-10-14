# Copyright 2024 Marimo. All rights reserved.
"""Registry of all supported MCP prompts."""

from marimo._mcp.server._prompts.base import PromptBase
from marimo._mcp.server._prompts.prompts.notebooks import ActiveNotebooks

SUPPORTED_MCP_PROMPTS: list[type[PromptBase]] = [
    ActiveNotebooks,
]
