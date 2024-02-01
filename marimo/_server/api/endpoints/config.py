# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os

import tomlkit
from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.requests import Request

from marimo import _loggers
from marimo._config.config import configure
from marimo._config.utils import get_config_path
from marimo._runtime import requests
from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
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
    config_path = get_config_path()
    config_dir = (
        os.path.dirname(config_path)
        if config_path
        else os.path.expanduser("~")
    )
    LOGGER.debug("Saving user configuration to %s", config_dir)
    config_path = os.path.join(config_dir, ".marimo.toml")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            tomlkit.dump(body.config, f)
    except Exception as e:
        raise HTTPException(
            HTTPStatus.SERVER_ERROR,
            detail="Failed to save file: {0}".format(str(e)),
        ) from e

    # Update the server's view of the config
    config = configure(body.config)
    if config["completion"]["copilot"]:
        LOGGER.debug("Starting copilot server")
        await app_state.session_manager.start_lsp_server()
    # Update the kernel's view of the config
    app_state.require_current_session().put_request(
        requests.ConfigurationRequest(str(body.config))
    )

    return SuccessResponse()
