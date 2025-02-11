# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import uuid4

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.websockets import WebSocket, WebSocketDisconnect

from marimo import _loggers
from marimo._mcp import registry
from marimo._messaging.ops import MCPEvaluationResult
from marimo._runtime.requests import MCPEvaluationRequest

# from marimo._server.api.deps import AppState
from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
from marimo._server.api.utils import parse_request
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.websockets import WebSocket
# server.py
from mcp import types
from mcp.server import Server

# from mcp.server.type import MCPEvaluationRequest, MCPEvaluationResult
from mcp.server.websocket import websocket_server
from pydantic.networks import AnyUrl

# Create an MCP server
mcp = Server("Demo")


# Add an addition tool
@mcp.call_tool()
async def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


"""
TODO:
- create an MCP using the session_view (this lives in the server)
- MCPEvaluate lives in the kernel
"""


@mcp.list_resources()
async def list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri=AnyUrl(f"file:///{name}.txt"),
            name=name,
            description=f"A sample text resource named {name}",
            mimeType="text/plain",
        )
        for name in ["greeting"]
    ]


LOGGER = _loggers.marimo_logger()

# Router for MCP
router = APIRouter()


@router.websocket("/ws")
async def mcp_websocket_endpoint(websocket: WebSocket) -> None:
    """Handle WebSocket connection and messages.

    Validates that the requested server exists and processes evaluation requests.
    """
    try:
        LOGGER.info("WebSocket connection established")
        app_state = AppState(websocket)
        LOGGER.warning("Starting MCP websocket server")
        async with websocket_server(
            scope=websocket.scope,
            receive=websocket.receive,
            send=websocket.send,
        ) as streams:
            await mcp.run(
                streams[0], streams[1], mcp.create_initialization_options()
            )

        session_id = app_state.query_params("session_id")
        assert session_id is not None, "session_id is required"
        session = app_state.session_manager.get_session(session_id)
        assert session is not None, "session not found"

        await websocket.accept()

        await asyncio.sleep(1)

        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                LOGGER.info("WebSocket disconnected")
                break
            except Exception as e:
                LOGGER.exception(e)
                continue
            LOGGER.info(f"Received message: {data}")

            if data["method"] == "initialize":
                LOGGER.info("Initializing MCP")
                await websocket.send_json(
                    {"type": "initialize_response", "result": "ok"}
                )
                continue

            session.put_mcp_evaluation_request(data)

            await websocket.send_json(
                MCPEvaluationResult(
                    mcp_evaluation_id=data["mcp_evaluation_id"],
                    result=data["result"],
                )
            )

    except Exception as e:
        LOGGER.exception(e)
        if not websocket.client_state.DISCONNECTED:
            await websocket.send_json({"type": "error", "error": str(e)})
