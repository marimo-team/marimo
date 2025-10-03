# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo._runtime.requests import (
    ClearCacheRequest,
    GetCacheInfoRequest,
)
from marimo._server.api.deps import AppState
from marimo._server.models.models import SuccessResponse
from marimo._server.router import APIRouter
from marimo._types.ids import ConsumerId

if TYPE_CHECKING:
    from starlette.requests import Request

# Router for cache endpoints
router = APIRouter()


@router.post("/clear")
@requires("edit")
async def clear_cache(request: Request) -> SuccessResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ClearCacheRequest"
    responses:
        200:
            description: Clear all caches
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    app_state.require_current_session().put_control_request(
        ClearCacheRequest(),
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )
    return SuccessResponse(success=True)


@router.post("/info")
@requires("edit")
async def get_cache_info(request: Request) -> SuccessResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/GetCacheInfoRequest"
    responses:
        200:
            description: Get cache statistics
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    app_state.require_current_session().put_control_request(
        GetCacheInfoRequest(),
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )
    return SuccessResponse(success=True)
