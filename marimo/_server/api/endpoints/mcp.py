# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import uuid4

# server.py
from mcp.server import Server
from mcp.server.websocket import websocket_server

# Create an MCP server
mcp = Server("Demo")


# Add an addition tool
@mcp.call_tool()
async def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


# Add a dynamic greeting resource
@mcp.read_resource("greeting://{name}")
async def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"


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
        session_id = app_state.query_params("session_id")
        assert session_id is not None, "session_id is required"
        session = app_state.session_manager.get_session(session_id)
        assert session is not None, "session not found"

        await websocket.accept()

        await asyncio.sleep(1)

        # Maybe use websocket_server, or pull from

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


# @router.get("/servers")
# @requires("edit")
# async def list_servers(request: Request) -> JSONResponse:  # noqa: ARG001
#     """List all registered MCP servers with their capabilities.

#     Returns a JSON response containing:
#     - List of servers with their names
#     - Each server's available tools, resources, and prompts
#     """
#     servers = registry.list_servers()
#     return JSONResponse({"servers": servers})


# @router.post("/evaluate")
# @requires("edit")
# async def mcp_evaluate(request: Request) -> JSONResponse:
#     """
#     requestBody:
#         content:
#             application/json:
#                 schema:
#                     $ref: "#/components/schemas/MCPEvaluationRequest"
#     responses:
#         200:
#             description: Evaluate an MCP server request
#             content:
#                 application/json:
#                     schema:
#                         $ref: "#/components/schemas/MCPEvaluationResult"
#     """
#     # app_state = AppState(request)
#     # session = app_state.require_current_session()

#     body = await parse_request(request, cls=MCPEvaluationRequest)
#     server_name = body.server_name
#     function_type = body.request_type  # tool, resource, or prompt
#     function_name = body.name
#     args = body.args

#     if not server_name or not function_type or not function_name:
#         raise HTTPException(
#             status_code=HTTPStatus.BAD_REQUEST,
#             detail="Missing required fields",
#         )

#     # Look up the server directly from the registry
#     server = registry.get_server(server_name)
#     if not server:
#         raise HTTPException(
#             status_code=HTTPStatus.NOT_FOUND,
#             detail=f"Server '{server_name}' not found",
#         )

#     # Create the evaluation request with a unique ID
#     mcp_request = MCPEvaluationRequest(
#         mcp_evaluation_id=str(uuid4()),
#         server_name=server_name,
#         request_type=function_type,
#         name=function_name,
#         args=args,
#     )

#     try:
#         # Evaluate the request directly using the server
#         result = await server.evaluate_request(mcp_request)

#         # Extract the result value
#         result_value = (
#             result.result
#             if isinstance(result, MCPEvaluationResult)
#             else result
#         )

#         return JSONResponse(
#             {
#                 "mcp_evaluation_id": mcp_request.mcp_evaluation_id,
#                 "result": result_value,
#             }
#         )

#     except Exception as e:
#         raise HTTPException(
#             status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
#             detail=str(e),
#         ) from None
