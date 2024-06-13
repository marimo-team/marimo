# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo import _loggers
from marimo._runtime.requests import SetUserConfigRequest
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import (
    BaseResponse,
    SaveUserConfigurationRequest,
    SuccessResponse,
)
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for config endpoints
router = APIRouter()


@router.post("/save_user_config")
@requires("edit")
async def save_user_config(
    *,
    request: Request,
) -> BaseResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/SaveUserConfigurationRequest"
    responses:
        200:
            description: Update the user config on disk and in the kernel. Only allowed in edit mode.
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """  # noqa: E501
    app_state = AppState(request)
    body = await parse_request(request, cls=SaveUserConfigurationRequest)
    config = app_state.config_manager.save_config(body.config)

    # Update the server's view of the config
    if config["completion"]["copilot"]:
        LOGGER.debug("Starting copilot server")
        await app_state.session_manager.start_lsp_server()

    # Update the kernel's view of the config
    # Session could be None if the user is on the home page
    session = app_state.get_current_session()
    if session is not None:
        session.put_control_request(SetUserConfigRequest(body.config))
    return SuccessResponse()
