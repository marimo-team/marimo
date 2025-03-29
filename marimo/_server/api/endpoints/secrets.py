# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo import _loggers
from marimo._runtime.requests import ListSecretKeysRequest
from marimo._server.api.deps import AppState
from marimo._server.models.models import BaseResponse, SuccessResponse
from marimo._server.router import APIRouter
from marimo._types.ids import ConsumerId

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for secrets endpoints
router = APIRouter()


@router.post("/keys")
@requires("edit")
async def list_keys(request: Request) -> SuccessResponse:
    """
    responses:
        200:
            description: Preview a column in a dataset
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/ListSecretKeysResponse"
    """
    app_state = AppState(request)
    app_state.require_current_session().put_control_request(
        ListSecretKeysRequest(),
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )
    return SuccessResponse(success=True)


@router.post("/create")
@requires("edit")
async def create_secret(request: Request) -> BaseResponse:
    """
    responses:
        200:
            description: Create a secret
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/BaseResponse"
    """
    del request
    raise NotImplementedError("Not implemented")


@router.post("/delete")
@requires("edit")
async def delete_secret(request: Request) -> BaseResponse:
    """
    responses:
        200:
            description: Delete a secret
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/BaseResponse"
    """
    del request
    raise NotImplementedError("Not implemented")
