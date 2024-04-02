# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from starlette.authentication import requires
from starlette.requests import Request

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import (
    BaseResponse,
    SaveUserConfigurationRequest,
    SuccessResponse,
)
from marimo._server.router import APIRouter

LOGGER = _loggers.marimo_logger()

# Router for config endpoints
router = APIRouter()


@router.post("/save_user_config")
@requires("edit")
async def save_user_config(
    *,
    request: Request,
) -> BaseResponse:
    """Run multiple cells (and their descendants).

    Updates cell code in the kernel if needed; registers new cells
    for unseen cell IDs.

    Only allowed in edit mode.
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=SaveUserConfigurationRequest)
    config = app_state.config_manager.save_config(body.config)

    # Update the server's view of the config
    if config["completion"]["copilot"]:
        LOGGER.debug("Starting copilot server")
        await app_state.session_manager.start_lsp_server()

    return SuccessResponse()
