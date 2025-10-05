# Copyright 2024 Marimo. All rights reserved.
"""
MCP (Model Context Protocol) Server Implementation for Marimo

This module implements an MCP server that provides LLMs with access to marimo
notebook context and functionality.
"""

from typing import TYPE_CHECKING

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools_registry import SUPPORTED_BACKEND_AND_MCP_TOOLS
from marimo._loggers import marimo_logger

LOGGER = marimo_logger()


if TYPE_CHECKING:
    from starlette.applications import Starlette


def setup_mcp_server(app: "Starlette") -> None:
    """Create and configure MCP server for marimo integration.

    Args:
        app: Starlette application instance for accessing marimo state
        server_name: Name for the MCP server instance
        stateless_http: Whether to use stateless HTTP mode

    Returns:
        StreamableHTTPSessionManager: MCP session manager
    """
    from mcp.server.fastmcp import FastMCP
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse
    from starlette.routing import Mount
    from starlette.types import Receive, Scope, Send

    mcp = FastMCP(
        "marimo-mcp-server",
        stateless_http=True,
        log_level="WARNING",
        # Change base path from /mcp to /server
        streamable_http_path="/server",
    )

    # Register all tools
    context = ToolContext(app=app)
    for tool in SUPPORTED_BACKEND_AND_MCP_TOOLS:
        tool_with_context = tool(context)
        mcp.tool()(tool_with_context.as_mcp_tool_fn())

    # Initialize streamable HTTP app
    mcp_app = mcp.streamable_http_app()

    # Middleware to require edit scope
    class RequiresEditMiddleware(BaseHTTPMiddleware):
        async def __call__(
            self, scope: Scope, receive: Receive, send: Send
        ) -> None:
            auth = scope.get("auth")
            if auth is None or "edit" not in auth.scopes:
                response = JSONResponse(
                    {"detail": "Forbidden"},
                    status_code=403,
                )
                return await response(scope, receive, send)

            return await self.app(scope, receive, send)

    mcp_app.add_middleware(RequiresEditMiddleware)

    # Add to the top of the routes to avoid conflicts with other routes
    app.routes.insert(0, Mount("/mcp", mcp_app))
    app.state.mcp = mcp
