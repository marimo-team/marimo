# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from collections.abc import Awaitable, MutableMapping

from marimo import _loggers
from marimo._server.api.deps import AppStateBase
from marimo._server.router import APIRouter

LOGGER = _loggers.marimo_logger()


# NOTE: This endpoint deviates from standard Marimo endpoint patterns because
# MCP (Model Context Protocol) requires direct ASGI stream control for its
# specialized JSON-RPC over HTTP transport. Standard Request/Response patterns
# would break MCP's session management and streaming capabilities.
class MCPRouter(APIRouter):
    """ASGI app that forwards /mcp traffic to the MCP session manager."""

    def __init__(self, prefix: str = "") -> None:
        super().__init__(prefix=prefix)

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ) -> None:
        root_app = scope.get("app")
        mcp_handler = None
        if root_app is not None:
            app_state = AppStateBase.from_app(root_app)
            mcp_handler = app_state.mcp_handler

        if mcp_handler is None:
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"text/plain")],
                }
            )
            await send(
                {"type": "http.response.body", "body": b"MCP not available"}
            )
            return

        # IMPORTANT: Do not touch scope["path"]; Mount already set root_path="/mcp"
        await mcp_handler(scope, receive, send)


# Create the MCP router instance
router = MCPRouter()
