"""WebSocket handler for MCP server updates."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from starlette.endpoints import WebSocketEndpoint

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

from marimo._server.api.endpoints.mcp import mcp_servers


class MCPWebSocket(WebSocketEndpoint):
    """WebSocket endpoint for MCP server updates."""

    encoding = "json"

    async def on_connect(self, websocket: WebSocket) -> None:
        """Handle WebSocket connection."""
        await websocket.accept()
        websocket.scope["servers"] = []

    async def on_receive(
        self, websocket: WebSocket, data: Dict[str, Any]
    ) -> None:
        """Handle incoming WebSocket messages."""
        message_type = data.get("type")
        server_name = data.get("server")

        if not server_name or not message_type:
            await websocket.send_json(
                {"type": "error", "error": "Missing server or message type"}
            )
            return

        server = mcp_servers.get(server_name)
        if not server:
            await websocket.send_json(
                {"type": "error", "error": f"Server {server_name} not found"}
            )
            return

        try:
            if message_type == "tool":
                name = data.get("name")
                args = data.get("args", {})
                result = await server.call_tool(name, **args)
                await websocket.send_json({"type": "result", "result": result})

            elif message_type == "resource":
                name = data.get("name")
                args = data.get("args", {})
                result = await server.call_resource(name, **args)
                await websocket.send_json({"type": "result", "result": result})

            elif message_type == "prompt":
                name = data.get("name")
                args = data.get("args", {})
                result = await server.call_prompt(name, **args)
                await websocket.send_json({"type": "result", "result": result})

            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "error": f"Unknown message type {message_type}",
                    }
                )

        except Exception as e:
            await websocket.send_json({"type": "error", "error": str(e)})
