# Copyright 2024 Marimo. All rights reserved.
"""
MCP (Model Context Protocol) Server Implementation for Marimo

This module implements an MCP server that provides LLMs with access to marimo
notebook context and functionality.
"""

from typing import TYPE_CHECKING

from starlette.routing import Mount

from marimo._loggers import marimo_logger

LOGGER = marimo_logger()

if TYPE_CHECKING:
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette


def setup_mcp_server(app: "Starlette") -> "StreamableHTTPSessionManager":
    """Create and configure MCP server for marimo integration.

    Args:
        app: Starlette application instance for accessing marimo state
        server_name: Name for the MCP server instance
        stateless_http: Whether to use stateless HTTP mode

    Returns:
        StreamableHTTPSessionManager: MCP session manager
    """

    # Lazily import here to raise import errors if mcp is not installed
    # The import errors will get caught by the marimo/_mcp/server/lifespan.py
    from mcp.server.fastmcp import FastMCP

    from marimo._mcp.server.tools.cells import register_cells_tools
    from marimo._mcp.server.tools.notebooks import register_notebooks_tools

    mcp = FastMCP(
        "marimo-mcp-server",
        stateless_http=True,
        log_level="WARNING",
    )

    # Change base path from /mcp to /server
    mcp.settings.streamable_http_path = "/server"

    # Register all tools
    register_notebooks_tools(mcp, app)
    register_cells_tools(mcp, app)

    # Initialize streamable HTTP app
    mcp_app = mcp.streamable_http_app()

    # Add to the top of the routes to avoid conflicts with other routes
    app.routes.insert(0, Mount("/mcp", mcp_app))

    return mcp.session_manager
