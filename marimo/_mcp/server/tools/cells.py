# Copyright 2025 Marimo. All rights reserved.

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from marimo._ai.tools.tools.cells import (
    GetCellRuntimeData,
    GetLightweightCellMap,
)


def register_cells_tools(mcp: FastMCP, app: Starlette) -> None:
    """Register cell-level management tools"""

    mcp.tool()(GetLightweightCellMap(app).as_mcp_tool_fn())
    mcp.tool()(GetCellRuntimeData(app).as_mcp_tool_fn())
