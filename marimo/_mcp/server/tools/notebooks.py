# Copyright 2025 Marimo. All rights reserved.

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.notebooks import GetActiveNotebooks


def register_notebooks_tools(mcp: FastMCP, app: Starlette) -> None:
    """Register notebook-level management tools"""

    context = ToolContext(app=app)

    mcp.tool()(GetActiveNotebooks(context).as_mcp_tool_fn())
