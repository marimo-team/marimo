# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict
from uuid import uuid4

from starlette.authentication import requires
from starlette.endpoints import WebSocketEndpoint
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket

from marimo import _loggers
from marimo._mcp import registry
from marimo._messaging.ops import MCPEvaluationResult
from marimo._runtime.requests import MCPEvaluationRequest

# from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
from marimo._server.api.utils import parse_request
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.websockets import WebSocket

LOGGER = _loggers.marimo_logger()

# Router for MCP
router = APIRouter()


class MCPWebSocket(WebSocketEndpoint):
    encoding = "json"

    async def on_connect(self, websocket: WebSocket) -> None:
        """Handle WebSocket connection.

        Validates that the requested server exists and stores it in the websocket scope.
        """
        try:
            server_name = websocket.path_params["server_name"]
            server = registry.get_server(server_name)
            if not server:
                await websocket.close(
                    code=4004, reason=f"Server '{server_name}' not found"
                )
                return

            # Store server before accepting connection
            websocket.scope["server"] = server
            await websocket.accept()
        except Exception as e:
            LOGGER.error(f"Error in MCP WebSocket connection: {str(e)}")
            await websocket.close(code=4000, reason="Internal server error")
            return

    async def on_receive(
        self, websocket: WebSocket, data: Dict[str, Any]
    ) -> None:
        """Handle incoming WebSocket messages.

        Processes evaluation requests and sends back results.
        """
        try:
            server = websocket.scope["server"]
            if data.get("type") == "evaluate":
                # Create a unique ID for this evaluation request
                mcp_evaluation_id = str(uuid4())

                # Create and process the evaluation request
                request = MCPEvaluationRequest(
                    server_name=server.name,
                    mcp_evaluation_id=mcp_evaluation_id,
                    request_type=data.get("request_type"),
                    name=data.get("name"),
                    args=data.get("args", {}),
                )

                # Evaluate the request
                result = await server.evaluate_request(request)

                # Send the result back
                await websocket.send_json(
                    {
                        "type": "evaluation_result",
                        "mcp_evaluation_id": mcp_evaluation_id,
                        "result": result.result
                        if isinstance(result, MCPEvaluationResult)
                        else result,
                    }
                )
        except Exception as e:
            LOGGER.error(f"Error in MCP WebSocket message handling: {str(e)}")
            await websocket.send_json({"type": "error", "error": str(e)})


@router.get("/servers")
async def list_servers(request: Request) -> JSONResponse:  # noqa: ARG001
    """List all registered MCP servers with their capabilities.

    Returns a JSON response containing:
    - List of servers with their names
    - Each server's available tools, resources, and prompts
    """
    servers = registry.list_servers()
    return JSONResponse({"servers": servers})


@router.post("/evaluate")
@requires("edit")
async def mcp_evaluate(request: Request) -> JSONResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/MCPEvaluationRequest"
    responses:
        200:
            description: Evaluate an MCP server request
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/MCPEvaluationResult"
    """
    # app_state = AppState(request)
    # session = app_state.require_current_session()

    body = await parse_request(request, cls=MCPEvaluationRequest)
    server_name = body.server_name
    function_type = body.request_type  # tool, resource, or prompt
    function_name = body.name
    args = body.args

    if not server_name or not function_type or not function_name:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Missing required fields",
        )

    # Look up the server directly from the registry
    server = registry.get_server(server_name)
    if not server:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Server '{server_name}' not found",
        )

    # Create the evaluation request with a unique ID
    mcp_request = MCPEvaluationRequest(
        mcp_evaluation_id=str(uuid4()),
        server_name=server_name,
        request_type=function_type,
        name=function_name,
        args=args,
    )

    try:
        # Evaluate the request directly using the server
        result = await server.evaluate_request(mcp_request)

        # Extract the result value
        result_value = (
            result.result
            if isinstance(result, MCPEvaluationResult)
            else result
        )

        return JSONResponse(
            {
                "mcp_evaluation_id": mcp_request.mcp_evaluation_id,
                "result": result_value,
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from None


# Add WebSocket route
router.routes.append(WebSocketRoute("/ws/{server_name}", MCPWebSocket))
