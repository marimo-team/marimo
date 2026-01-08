# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import PlainTextResponse

from marimo import _loggers
from marimo._runtime.commands import RenameNotebookCommand
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import (
    BaseResponse,
    CopyNotebookRequest,
    ReadCodeResponse,
    RenameNotebookRequest,
    SaveAppConfigurationRequest,
    SaveNotebookRequest,
    SuccessResponse,
)
from marimo._server.router import APIRouter
from marimo._types.ids import ConsumerId
from marimo._utils.async_path import abspath
from marimo._utils.http import HTTPStatus

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for file endpoints
router = APIRouter()


@router.post("/read_code")
@requires("read")
async def read_code(
    *,
    request: Request,
) -> ReadCodeResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    responses:
        200:
            description: Read the code from the server
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/ReadCodeResponse"
        400:
            description: File must be saved before downloading
        403:
            description: Code is not available in run mode
    """
    app_state = AppState(request)

    # Check if code should be visible (edit mode or include_code=True)
    if not app_state.session_manager.should_send_code_to_frontend():
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Code is not available",
        )

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
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/RenameNotebookRequest"
    responses:
        200:
            description: Rename the current app
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    body = await parse_request(request, cls=RenameNotebookRequest)
    app_state = AppState(request)

    # Resolve relative filenames against the file router's directory
    if not Path(body.filename).is_absolute():
        directory = app_state.session_manager.file_router.directory
        if directory:
            body.filename = str(Path(directory) / body.filename)

    filename = await abspath(body.filename)

    app_state.require_current_session().put_control_request(
        RenameNotebookCommand(filename=filename),
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )

    await app_state.session_manager.rename_session(
        app_state.require_current_session_id(), body.filename
    )

    return SuccessResponse()


@router.post("/save")
@requires("edit")
async def save(
    *,
    request: Request,
) -> PlainTextResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
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

    # Resolve relative filenames against the file router's directory
    if body.filename and not Path(body.filename).is_absolute():
        directory = app_state.session_manager.file_router.directory
        if directory:
            body.filename = str(Path(directory) / body.filename)

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
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
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

    # Resolve relative filenames against the file router's directory
    if body.destination and not Path(body.destination).is_absolute():
        directory = app_state.session_manager.file_router.directory
        if directory:
            body.destination = str(Path(directory) / body.destination)

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
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
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
