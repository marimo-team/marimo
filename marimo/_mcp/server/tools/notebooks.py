# Copyright 2025 Marimo. All rights reserved.

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from marimo._ai.tools.tools.notebooks import GetActiveNotebooks


def register_notebooks_tools(mcp: FastMCP, app: Starlette) -> None:
    """Register notebook-level management tools"""

    mcp.tool()(GetActiveNotebooks(app).as_mcp_tool_fn())
