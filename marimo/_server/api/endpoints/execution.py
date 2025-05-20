# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from starlette.authentication import requires
from starlette.responses import JSONResponse

from marimo import _loggers
from marimo._messaging.ops import Alert
from marimo._runtime.requests import (
    ExecuteScratchpadRequest,
    FunctionCallRequest,
    HTTPRequest,
    PdbRequest,
    SetModelMessageRequest,
    SetUIElementValueRequest,
)
from marimo._server.api.deps import AppState
from marimo._server.api.endpoints.ws import DOC_MANAGER, FILE_QUERY_PARAM_KEY
from marimo._server.api.utils import parse_request
from marimo._server.file_router import MarimoFileKey
from marimo._server.models.models import (
    BaseResponse,
    InstantiateRequest,
    RunRequest,
    SuccessResponse,
    UpdateComponentValuesRequest,
)
from marimo._server.router import APIRouter
from marimo._server.uvicorn_utils import close_uvicorn
from marimo._types.ids import ConsumerId

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for execution endpoints
router = APIRouter()


@router.post("/set_ui_element_value")
async def set_ui_element_values(
    *,
    request: Request,
) -> BaseResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/UpdateComponentValuesRequest"
    responses:
        200:
            description: Set UI element values
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=UpdateComponentValuesRequest)
    app_state.require_current_session().put_control_request(
        SetUIElementValueRequest(
            object_ids=body.object_ids,
            values=body.values,
            token=str(uuid4()),
            request=HTTPRequest.from_request(request),
        ),
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )

    return SuccessResponse()


@router.post("/set_model_value")
async def set_model_values(
    *,
    request: Request,
) -> BaseResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/SetModelMessageRequest"
    responses:
        200:
            description: Set model value
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=SetModelMessageRequest)
    app_state.require_current_session().put_control_request(
        body,
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )

    return SuccessResponse()


@router.post("/instantiate")
async def instantiate(
    *,
    request: Request,
) -> BaseResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/InstantiateRequest"
    responses:
        200:
            description: Instantiate a component
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=InstantiateRequest)
    app_state.require_current_session().instantiate(
        body,
        http_request=HTTPRequest.from_request(request),
    )

    return SuccessResponse()


@router.post("/function_call")
async def function_call(
    *,
    request: Request,
) -> BaseResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/FunctionCallRequest"
    responses:
        200:
            description: Invoke an RPC
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=FunctionCallRequest)
    app_state.require_current_session().put_control_request(
        body,
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )

    return SuccessResponse()


@router.post("/interrupt")
@requires("edit")
async def interrupt(
    *,
    request: Request,
) -> BaseResponse:
    """
    responses:
        200:
            description: Interrupt the kernel's execution
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    app_state.require_current_session().try_interrupt()

    return SuccessResponse()


@router.post("/run")
@requires("edit")
async def run_cell(
    *,
    request: Request,
) -> BaseResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/RunRequest"
    responses:
        200:
            description: Run a cell. Updates cell code in the kernel if needed; registers new cells for unseen cell IDs. Only allowed in edit mode.
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """  # noqa: E501
    app_state = AppState(request)
    body = await parse_request(request, cls=RunRequest)
    body.request = HTTPRequest.from_request(request)
    app_state.require_current_session().put_control_request(
        body.as_execution_request(),
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )

    return SuccessResponse()


@router.post("/scratchpad/run")
@requires("edit")
async def run_scratchpad(
    *,
    request: Request,
) -> BaseResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ExecuteScratchpadRequest"
    responses:
        200:
            description: Run the scratchpad
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """  # noqa: E501
    app_state = AppState(request)
    body = await parse_request(request, cls=ExecuteScratchpadRequest)
    app_state.require_current_session().put_control_request(
        body,
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )

    return SuccessResponse()


@router.post("/pdb/pm")
@requires("edit")
async def run_post_mortem(
    *,
    request: Request,
) -> BaseResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/PdbRequest"
    responses:
        200:
            description: Run a post mortem on the most recent failed cell.
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """  # noqa: E501
    app_state = AppState(request)
    body = await parse_request(request, cls=PdbRequest)
    app_state.require_current_session().put_control_request(
        body,
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )

    return SuccessResponse()


@router.post("/restart_session")
@requires("edit")
async def restart_session(
    *,
    request: Request,
) -> BaseResponse:
    """
    responses:
        200:
            description: Restart the current session without affecting other sessions.
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """  # noqa: E501
    app_state = AppState(request)
    session_manager = app_state.session_manager

    # This just closes the session, and the frontend will
    # do a full reload, which will restart the session.
    session_id = app_state.require_current_session_id()
    session = app_state.require_current_session()
    session_manager.close_session(session_id)

    # Close RTC doc if it exists
    file_key: Optional[MarimoFileKey] = (
        app_state.query_params(FILE_QUERY_PARAM_KEY)
        or session_manager.file_router.get_unique_file_key()
        or session.app_file_manager.path
    )
    if file_key is not None:
        await DOC_MANAGER.remove_doc(file_key)
    else:
        LOGGER.warning("Unable to close RTC doc as no file key was provided")

    return SuccessResponse()


@router.post("/shutdown")
@requires("edit")
async def shutdown(
    *,
    request: Request,
) -> BaseResponse:
    """
    responses:
        200:
            description: Shutdown the kernel
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    LOGGER.debug("Received shutdown request")
    app_state = AppState(request)
    session_manager = app_state.session_manager
    file_router = session_manager.file_router

    def shutdown_server() -> None:
        app_state.session_manager.shutdown()
        close_uvicorn(app_state.server)

    # If we are only operating on a single file (new or explicit file),
    # and there are no other sessions (user may have opened another notebook
    # from the file explorer) then we should shutdown the whole server
    key = file_router.get_unique_file_key()
    if key and len(session_manager.sessions) <= 1:
        shutdown_server()
        return SuccessResponse()

    # Otherwise, get the session
    session_id = app_state.get_current_session_id()
    if not session_id:
        shutdown_server()
        return SuccessResponse()

    was_shutdown = session_manager.close_session(session_id)
    if not was_shutdown:
        shutdown_server()

    return SuccessResponse()


@router.post("/takeover")
@requires("edit")
async def takeover_endpoint(
    *,
    request: Request,
) -> JSONResponse:
    """
    responses:
    200:
        description: Successfully closed existing sessions
        content:
            application/json:
                schema:
                    type: object
                    properties:
                        status:
                            type: string
    """
    app_state = AppState(request)

    file_key: Optional[MarimoFileKey] = (
        app_state.query_params(FILE_QUERY_PARAM_KEY)
        or app_state.session_manager.file_router.get_unique_file_key()
    )
    if file_key is None:
        LOGGER.error("No file key provided")
        return JSONResponse(
            status_code=400,
            content={"error": "Cannot take over session."},
        )

    # Find and close any existing sessions for this file
    existing_session = app_state.session_manager.get_session_by_file_key(
        file_key
    )
    if existing_session is not None:
        # Send a disconnect message to the client
        existing_session.write_operation(
            Alert(
                title="Session taken over",
                description="Another user has taken over this session.",
                variant="danger",
            ),
            from_consumer_id=None,
        )
        # Wait 100ms to ensure the client has received the message
        await asyncio.sleep(0.1)
        existing_session.maybe_disconnect_consumer()
    else:
        LOGGER.warning("No existing session found for file key %s", file_key)

    return JSONResponse(status_code=200, content={"status": "ok"})
