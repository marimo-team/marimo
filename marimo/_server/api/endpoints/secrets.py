# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo import _loggers
from marimo._runtime.requests import (
    ListSecretKeysRequest,
    RefreshSecretsRequest,
)
from marimo._secrets.secrets import write_secret
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import BaseResponse, SuccessResponse
from marimo._server.models.secrets import CreateSecretRequest
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
    requestBody:
        required: true
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ListSecretKeysRequest"
    responses:
        200:
            description: List all secret keys
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/ListSecretKeysResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=ListSecretKeysRequest)
    app_state.require_current_session().put_control_request(
        body,
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )
    return SuccessResponse(success=True)


@router.post("/create")
@requires("edit")
async def create_secret(request: Request) -> BaseResponse:
    """
    requestBody:
        required: true
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/CreateSecretRequest"
    responses:
        200:
            description: Create a secret
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/BaseResponse"
    """
    body = await parse_request(request, cls=CreateSecretRequest)
    app_state = AppState(request)
    session_id = app_state.require_current_session_id()

    # Write to the provider
    write_secret(body, app_state.config_manager.get_config(hide_secrets=False))

    # Refresh the secrets
    app_state.require_current_session().put_control_request(
        RefreshSecretsRequest(),
        from_consumer_id=ConsumerId(session_id),
    )
    return SuccessResponse(success=True)


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
