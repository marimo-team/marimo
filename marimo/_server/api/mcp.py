"""MCP API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.endpoints import HTTPEndpoint, WebSocketEndpoint
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

from marimo._mcp.server import registry


class ListServersEndpoint(HTTPEndpoint):
    async def get(self, request):
        """List all registered MCP servers."""
        servers = registry.list_servers()
        return JSONResponse({"servers": servers})


class MCPWebSocket(WebSocketEndpoint):
    encoding = "json"

    async def on_connect(self, websocket: WebSocket) -> None:
        server_name = websocket.path_params["server_name"]
        server = registry.get_server(server_name)
        if not server:
            await websocket.close(code=4004, reason="Server not found")
            return
        await websocket.accept()
        websocket.scope["server"] = server

    async def on_receive(self, websocket: WebSocket, data) -> None:
        server = websocket.scope["server"]
        try:
            if data.get("type") == "execute_tool":
                tool_name = data.get("tool")
                args = data.get("args", {})
                result = await server.execute_tool(tool_name, **args)
                await websocket.send_json(
                    {"type": "tool_result", "result": result}
                )
            elif data.get("type") == "execute_resource":
                resource_name = data.get("resource")
                args = data.get("args", {})
                result = await server.execute_resource(resource_name, **args)
                await websocket.send_json(
                    {"type": "resource_result", "result": result}
                )
            elif data.get("type") == "execute_prompt":
                prompt_name = data.get("prompt")
                args = data.get("args", {})
                result = await server.execute_prompt(prompt_name, **args)
                await websocket.send_json(
                    {"type": "prompt_result", "result": result}
                )
        except Exception as e:
            await websocket.send_json({"type": "error", "error": str(e)})


routes = [
    Route("/servers", ListServersEndpoint),
    WebSocketRoute("/ws/{server_name}", MCPWebSocket),
]
