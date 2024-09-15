# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import PlainTextResponse

from marimo import _loggers
from marimo._ast import codegen
from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
from marimo._server.api.utils import parse_request
from marimo._server.models.models import (
    BaseResponse,
    CopyNotebookRequest,
    OpenFileRequest,
    ReadCodeResponse,
    RenameFileRequest,
    SaveAppConfigurationRequest,
    SaveNotebookRequest,
    SuccessResponse,
)
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for file endpoints
router = APIRouter()


@router.post("/read_code")
@requires("edit")
async def read_code(
    *,
    request: Request,
) -> ReadCodeResponse:
    """
    responses:
        200:
            description: Read the code from the server
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/ReadCodeResponse"
        400:
            description: File must be saved before downloading
    """
    app_state = AppState(request)
    session = app_state.require_current_session()

    if not session.app_file_manager.path:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="File must be saved before downloading",
        )

    contents = session.app_file_manager.read_file()

    return ReadCodeResponse(contents=contents)


@router.post("/rename")
@requires("edit")
async def rename_file(
    *,
    request: Request,
) -> BaseResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/RenameFileRequest"
    responses:
        200:
            description: Rename the current app
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    body = await parse_request(request, cls=RenameFileRequest)
    app_state = AppState(request)
    session = app_state.require_current_session()
    prev_path = session.app_file_manager.path

    session.app_file_manager.rename(body.filename)
    new_path = session.app_file_manager.path

    if prev_path and new_path:
        app_state.session_manager.recents.rename(prev_path, new_path)
    elif new_path:
        app_state.session_manager.recents.touch(new_path)

    app_state.require_current_session().put_control_request(
        body.as_execution_request()
    )

    return SuccessResponse()


@router.post("/open")
@requires("edit")
async def open_file(
    *,
    request: Request,
) -> BaseResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/OpenFileRequest"
    responses:
        200:
            description: Open a file
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
        400:
            description: File does not exist
    """
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

    return SuccessResponse()


@router.post("/save")
@requires("edit")
async def save(
    *,
    request: Request,
) -> PlainTextResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/SaveNotebookRequest"
    responses:
        200:
            description: Save the current app
            content:
                text/plain:
                    schema:
                        type: string
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=SaveNotebookRequest)
    session = app_state.require_current_session()
    contents = session.app_file_manager.save(body)

    return PlainTextResponse(content=contents)


@router.post("/copy")
@requires("edit")
async def copy(
    *,
    request: Request,
) -> PlainTextResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/CopyNotebookRequest"
    responses:
        200:
            description: Copy notebook
            content:
                text/plain:
                    schema:
                        type: string
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=CopyNotebookRequest)
    session = app_state.require_current_session()
    contents = session.app_file_manager.copy(body)

    return PlainTextResponse(content=contents)


@router.post("/save_app_config")
@requires("edit")
async def save_app_config(
    *,
    request: Request,
) -> PlainTextResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/SaveAppConfigurationRequest"
    responses:
        200:
            description: Save the app configuration
            content:
                text/plain:
                    schema:
                        type: string
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=SaveAppConfigurationRequest)
    session = app_state.require_current_session()
    contents = session.app_file_manager.save_app_config(body.config)

    return PlainTextResponse(content=contents)
