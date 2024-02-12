# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.requests import Request

from marimo import _loggers
from marimo._ast import codegen
from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
from marimo._server.api.utils import parse_request
from marimo._server.model import SessionMode
from marimo._server.models.models import (
    BaseResponse,
    OpenFileRequest,
    ReadCodeResponse,
    RenameFileRequest,
    SaveAppConfigurationRequest,
    SaveRequest,
    SuccessResponse,
)
from marimo._server.print import print_startup
from marimo._server.router import APIRouter

LOGGER = _loggers.marimo_logger()

# Router for file endpoints
router = APIRouter()


@router.post("/read_code")
@requires("edit")
async def read_code(
    *,
    request: Request,
) -> ReadCodeResponse:
    app_state = AppState(request)
    """Handler for reading code from the server."""
    session = app_state.require_current_session()
    contents = session.app_file_manager.read_file()

    return ReadCodeResponse(contents=contents)


@router.post("/rename")
@requires("edit")
async def rename_file(
    *,
    request: Request,
) -> BaseResponse:
    """Rename the current app."""
    body = await parse_request(request, cls=RenameFileRequest)
    app_state = AppState(request)
    mgr = app_state.session_manager
    session = app_state.require_current_session()

    session.app_file_manager.rename(body.filename)
    mgr.rename(body.filename)

    return SuccessResponse()


@router.post("/open")
@requires("edit")
async def open_file(
    *,
    request: Request,
) -> BaseResponse:
    """Open a file."""
    app_state = AppState(request)
    body = await parse_request(request, cls=OpenFileRequest)

    # Validate file exists
    if not os.path.exists(body.path):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"File {body.path} does not exist",
        )

    # Get relative path
    filename = os.path.relpath(body.path)

    try:
        app = codegen.get_app(filename)
        if app is None:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"File {filename} is not a valid marimo app",
            )
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}",
        ) from e

    mgr = app_state.session_manager
    mgr.rename(filename)
    host = app_state.host
    port = app_state.port
    base_url = app_state.base_url
    run = app_state.mode == SessionMode.RUN
    print_startup(
        filename=filename, url=f"http://{host}:{port}{base_url}", run=run
    )

    return SuccessResponse()


@router.post("/save")
@requires("edit")
async def save(
    *,
    request: Request,
) -> BaseResponse:
    """Save the current app."""
    app_state = AppState(request)
    mgr = app_state.session_manager
    body = await parse_request(request, cls=SaveRequest)
    session = app_state.require_current_session()
    session.app_file_manager.save(body)

    if mgr.filename is None:
        mgr.rename(body.filename)

    return SuccessResponse()


@router.post("/save_app_config")
@requires("edit")
async def save_app_config(
    *,
    request: Request,
) -> BaseResponse:
    """Save the current app."""
    app_state = AppState(request)
    body = await parse_request(request, cls=SaveAppConfigurationRequest)
    session = app_state.require_current_session()
    session.app_file_manager.save_app_config(body.config)

    return SuccessResponse()
