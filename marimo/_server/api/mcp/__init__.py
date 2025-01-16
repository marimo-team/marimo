"""MCP API endpoints."""

from __future__ import annotations

from starlette.routing import WebSocketRoute

from marimo._server.api.endpoints.mcp import router
from marimo._server.api.mcp.ws import MCPWebSocket

# Include all routes from the router plus the WebSocket route
routes = [
    *router.routes,  # Spread all routes from the router
    WebSocketRoute("/ws", MCPWebSocket),
]
