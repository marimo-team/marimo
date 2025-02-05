# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from marimo import _loggers
from marimo._runtime.requests import MCPEvaluationRequest
from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
from marimo._server.api.utils import parse_request
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for MCP
router = APIRouter()


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
    app_state = AppState(request)
    session = app_state.get_current_session()
    # NOTE(mcp): or should we use require_current_session()?
    # session = app_state.require_current_session()

    if not session:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="No active session found",
        )

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

    mcp_request = MCPEvaluationRequest(
        mcp_evaluation_id=str(uuid4()),
        server_name=server_name,
        request_type=function_type,
        name=function_name,
        args=args,
    )

    # Put the request in the control queue
    session.put_control_request(mcp_request)

    # TODO(mcp): how to get the result?

    return JSONResponse({"result": "Request queued successfully"})
