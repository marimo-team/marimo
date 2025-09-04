# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from starlette.authentication import requires
from starlette.background import BackgroundTask
from starlette.responses import JSONResponse

from marimo import _loggers
from marimo._messaging.msgspec_encoder import asdict
from marimo._runtime.requests import SetUserConfigRequest
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import (
    SaveUserConfigurationRequest,
    SuccessResponse,
)
from marimo._server.router import APIRouter
from marimo._types.ids import ConsumerId

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
) -> JSONResponse:
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
    # Allow unknown keys to handle backward/forward compatibility
    body = await parse_request(
        request, cls=SaveUserConfigurationRequest, allow_unknown_keys=True
    )
    config = app_state.config_manager.save_config(body.config)

    background_task: Optional[BackgroundTask] = None
    # Update the server's view of the config
    if config["completion"]["copilot"]:
        LOGGER.debug("Starting copilot server")
        background_task = BackgroundTask(
            app_state.session_manager.start_lsp_server
        )

    # Update the kernel's view of the config
    # Session could be None if the user is on the home page
    session = app_state.get_current_session()
    if session is not None:
        session.put_control_request(
            SetUserConfigRequest(config),
            from_consumer_id=ConsumerId(
                app_state.require_current_session_id()
            ),
        )

    return JSONResponse(
        content=asdict(SuccessResponse()),
        background=background_task,
    )
