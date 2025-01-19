# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
from marimo._server.api.utils import parse_request
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for MCP
router = APIRouter()


# TODO(mcp): should rewrite this function
@router.post("/evaluate")
@requires("edit")
async def mcp_evaluate(request: Request) -> JSONResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/MCPServerEvaluationRequest"
    responses:
        200:
            description: Evaluate an MCP server request
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    session = app_state.get_current_session()

    if not session:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="No active session found",
        )

    body = await parse_request(request)
    server_name = body.get("server_name")
    function_type = body.get("request_type")  # tool, resource, or prompt
    function_name = body.get("name")
    args = body.get("args", {})

    if not server_name or not function_type or not function_name:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Missing required fields",
        )

    server = session.session_view.mcp_servers.get(server_name)
    if not server:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Server {server_name} not found",
        )

    try:
        if function_type == "tool":
            result = await server.call_tool(function_name, **args)
        elif function_type == "resource":
            result = await server.call_resource(function_name, **args)
        elif function_type == "prompt":
            result = await server.call_prompt(function_name, **args)
        else:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Invalid function type {function_type}",
            )
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    return JSONResponse({"result": result})
