# Copyright 2024 Marimo. All rights reserved.
"""
MCP (Model Context Protocol) Server Implementation for Marimo

This module implements an MCP server that provides LLMs with access to marimo
notebook context and functionality.
"""

from typing import TYPE_CHECKING

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
    from mcp.server.fastmcp import FastMCP

    from marimo._mcp.server.tools.cells import register_cells_tools
    from marimo._mcp.server.tools.notebooks import register_notebooks_tools

    mcp = FastMCP(
        "marimo-mcp-server",
        stateless_http=True,
        log_level="WARNING",
    )

    # Register all tools
    register_notebooks_tools(mcp, app)
    register_cells_tools(mcp, app)

    # Initialize streamable HTTP app to create session manager
    # This should be called before the session manager is used
    mcp.streamable_http_app()

    session_manager = mcp.session_manager

    return session_manager
