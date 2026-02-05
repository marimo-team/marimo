# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from starlette.authentication import requires
from starlette.background import BackgroundTask
from starlette.responses import JSONResponse

from marimo import _loggers
from marimo._config.config import PartialMarimoConfig
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.msgspec_encoder import asdict
from marimo._messaging.notification import MissingPackageAlertNotification
from marimo._runtime.commands import UpdateUserConfigCommand
from marimo._runtime.packages.utils import is_python_isolated
from marimo._server.ai.mcp.config import is_mcp_config_empty
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import (
    SaveUserConfigurationRequest,
    SuccessResponse,
)
from marimo._server.router import APIRouter
from marimo._session import send_message_to_consumer
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
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: false
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
    session_id = app_state.get_current_session_id()
    session = app_state.get_current_session()
    # Allow unknown keys to handle backward/forward compatibility
    body = await parse_request(
        request, cls=SaveUserConfigurationRequest, allow_unknown_keys=True
    )
    # TODO: we may want to validate deep-partial here, but validating with PartialMarimoConfig it too strict
    # so we just cast to PartialMarimoConfig
    config = app_state.config_manager.save_config(
        cast(PartialMarimoConfig, body.config)
    )

    async def handle_background_tasks() -> None:
        # Update the server's view of the config
        if config["completion"]["copilot"]:
            LOGGER.debug("Starting copilot server")
            await app_state.session_manager.start_lsp_server()

        # Reconfigure MCP servers if config changed
        mcp_config = config.get("mcp")

        # Handle missing MCP dependencies
        if (
            not is_mcp_config_empty(mcp_config)
            and not DependencyManager.mcp.has()
        ):
            # If we're in an edit session, send an package installation request
            if session_id is not None and session is not None:
                send_message_to_consumer(
                    session=session,
                    operation=MissingPackageAlertNotification(
                        packages=["mcp"],
                        isolated=is_python_isolated(),
                    ),
                    consumer_id=ConsumerId(session_id),
                )

        try:
            from marimo._server.ai.mcp import get_mcp_client

            if mcp_config and not is_mcp_config_empty(mcp_config):
                LOGGER.debug("Reconfiguring MCP servers with updated config")
                mcp_client = get_mcp_client()
                await mcp_client.configure(mcp_config)
                LOGGER.info(
                    f"MCP servers reconfigured: {list(mcp_client.servers.keys())}"
                )
        except Exception as e:
            LOGGER.warning(f"Failed to reconfigure MCP servers: {e}")

    background_task = BackgroundTask(handle_background_tasks)

    # Update the kernel's view of the config
    # Session could be None if the user is on the home page
    if session is not None:
        session.put_control_request(
            UpdateUserConfigCommand(config),
            from_consumer_id=ConsumerId(
                app_state.require_current_session_id()
            ),
        )

    return JSONResponse(
        content=asdict(SuccessResponse()),
        background=background_task,
    )
