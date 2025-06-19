# Copyright 2025 Marimo. All rights reserved.
from dataclasses import dataclass
from typing import Any, Literal

from marimo._config.config import CopilotMode

ToolSource = Literal["mcp", "local"]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    source: ToolSource  # special handling for mcp tools
    mode: list[
        CopilotMode
    ]  # tools can be made available in more than one mode


# TODO: Add ToolRegistry class to manage tool registration and retrieval
# TODO: Add ToolManager class to interact with tool registry,
# tool invoker, and expose tools to providers.py
# TODO: Add ToolInvoker class to handle calling tools
