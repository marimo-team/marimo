# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from starlette.authentication import requires
from starlette.requests import Request

from marimo import _loggers
from marimo._runtime.requests import (
    FunctionCallRequest,
    SetUIElementValueRequest,
)
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import (
    BaseResponse,
    InstantiateRequest,
    RunRequest,
    SuccessResponse,
    UpdateComponentValuesRequest,
)
from marimo._server.router import APIRouter
from marimo._server.uvicorn_utils import close_uvicorn

LOGGER = _loggers.marimo_logger()

# Router for execution endpoints
router = APIRouter()


@router.post("/set_ui_element_value")
async def set_ui_element_values(
    *,
    request: Request,
) -> BaseResponse:
    """
    Set UI element values.
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=UpdateComponentValuesRequest)
    app_state.require_current_session().put_control_request(
        SetUIElementValueRequest(body.zip())
    )
    return SuccessResponse()


@router.post("/instantiate")
async def instantiate(
    *,
    request: Request,
) -> BaseResponse:
    """
    Instantiate the kernel.
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=InstantiateRequest)
    app_state.require_current_session().instantiate(body)

    return SuccessResponse()


@router.post("/function_call")
async def function_call(
    *,
    request: Request,
) -> BaseResponse:
    """Invoke an RPC"""
    app_state = AppState(request)
    body = await parse_request(request, cls=FunctionCallRequest)
    app_state.require_current_session().put_control_request(body)

    return SuccessResponse()


@router.post("/interrupt")
@requires("edit")
async def interrupt(
    *,
    request: Request,
) -> BaseResponse:
    """Interrupt the kernel's execution."""
    app_state = AppState(request)
    app_state.require_current_session().try_interrupt()

    return SuccessResponse()


@router.post("/run")
@requires("edit")
async def run_cell(
    *,
    request: Request,
) -> BaseResponse:
    """Run multiple cells (and their descendants).

    Updates cell code in the kernel if needed; registers new cells
    for unseen cell IDs.

    Only allowed in edit mode.
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=RunRequest)
    app_state.require_current_session().put_control_request(
        body.as_execution_request()
    )

    return SuccessResponse()


@router.post("/restart_session")
@requires("edit")
async def restart_session(
    *,
    request: Request,
) -> BaseResponse:
    """
    Restart a session. This does not restart the
    kernel or affect other sessions
    """
    app_state = AppState(request)
    # This just closes the session, and the frontend will
    # do a full reload, which will restart the session.
    session_id = app_state.require_current_session_id()
    app_state.session_manager.close_session(session_id)

    return SuccessResponse()


@router.post("/shutdown")
@requires("edit")
async def shutdown(
    *,
    request: Request,
) -> BaseResponse:
    """Shutdown the kernel."""
    LOGGER.debug("Received shutdown request")
    app_state = AppState(request)
    session_manager = app_state.session_manager
    file_router = session_manager.file_router

    def shutdown_server() -> None:
        app_state.session_manager.shutdown()
        close_uvicorn(app_state.server)

    # If we are only operating on a single file (new or explicit file),
    # then we should shutdown the whole server
    key = file_router.get_unique_file_key()
    if key:
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
