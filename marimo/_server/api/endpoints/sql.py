# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo._runtime.requests import (
    ValidateSQLRequest,
)
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import BaseResponse, SuccessResponse
from marimo._server.router import APIRouter
from marimo._types.ids import ConsumerId

if TYPE_CHECKING:
    from starlette.requests import Request

# Router for SQL endpoints
router = APIRouter()


@router.post("/validate")
@requires("edit")
async def validate_sql(request: Request) -> BaseResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ValidateSQLRequest"
    responses:
        200:
            description: Validate an SQL query
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, ValidateSQLRequest)
    app_state.require_current_session().put_control_request(
        body,
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )
    return SuccessResponse()
