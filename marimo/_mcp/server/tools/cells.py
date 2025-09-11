# Copyright 2025 Marimo. All rights reserved.

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.cells import (
    GetCellRuntimeData,
    GetLightweightCellMap,
)


def register_cells_tools(mcp: FastMCP, app: Starlette) -> None:
    """Register cell-level management tools"""

    context = ToolContext(app=app)

    mcp.tool()(GetLightweightCellMap(context).as_mcp_tool_fn())
    mcp.tool()(GetCellRuntimeData(context).as_mcp_tool_fn())
