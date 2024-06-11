# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo import _loggers
from marimo._server.api.utils import parse_request
from marimo._server.files.os_file_system import OSFileSystem
from marimo._server.models.files import (
    FileCreateRequest,
    FileCreateResponse,
    FileDeleteRequest,
    FileDeleteResponse,
    FileDetailsRequest,
    FileDetailsResponse,
    FileListRequest,
    FileListResponse,
    FileMoveRequest,
    FileMoveResponse,
    FileUpdateRequest,
    FileUpdateResponse,
)
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for file system endpoints
router = APIRouter()

file_system = OSFileSystem()


@router.post("/list_files")
@requires("edit")
async def list_files(
    *,
    request: Request,
) -> FileListResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/FileListRequest"
    responses:
        200:
            description: List files and directories in a given path
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/FileListResponse"
    """
    body = await parse_request(request, cls=FileListRequest)
    root = body.path or file_system.get_root()
    files = file_system.list_files(root)
    return FileListResponse(files=files, root=root)


@router.post("/file_details")
@requires("edit")
async def file_details(
    *,
    request: Request,
) -> FileDetailsResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/FileDetailsRequest"
    responses:
        200:
            description: Get details of a specific file or directory
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/FileDetailsResponse"
    """
    body = await parse_request(request, cls=FileDetailsRequest)
    # This fails if the file isn't encoded as utf-8
    # TODO: support returning raw bytes
    return file_system.get_details(body.path)


@router.post("/create")
@requires("edit")
async def create_file_or_directory(
    *,
    request: Request,
) -> FileCreateResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/FileCreateRequest"
    responses:
        200:
            description: Create a new file or directory
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/FileCreateResponse"
    """
    body = await parse_request(request, cls=FileCreateRequest)
    try:
        decoded_contents = (
            base64.b64decode(body.contents)
            if body.contents is not None
            else None
        )

        info = file_system.create_file_or_directory(
            body.path, body.type, body.name, decoded_contents
        )
        return FileCreateResponse(success=True, info=info)
    except Exception as e:
        LOGGER.error(f"Error creating file or directory: {e}")
        return FileCreateResponse(success=False, message=str(e))


@router.post("/delete")
@requires("edit")
async def delete_file_or_directory(
    *,
    request: Request,
) -> FileDeleteResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/FileDeleteRequest"
    responses:
        200:
            description: Delete a file or directory
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/FileDeleteResponse"
    """
    body = await parse_request(request, cls=FileDeleteRequest)
    try:
        file_system.get_details(body.path)
        success = file_system.delete_file_or_directory(body.path)
        return FileDeleteResponse(success=success)
    except Exception as e:
        LOGGER.error(f"Error deleting file or directory: {e}")
        return FileDeleteResponse(success=False, message=str(e))


@router.post("/move")
@requires("edit")
async def move_file_or_directory(
    *,
    request: Request,
) -> FileMoveResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/FileMoveRequest"
    responses:
        200:
            description: Move a file or directory
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/FileMoveResponse"
    """
    body = await parse_request(request, cls=FileMoveRequest)
    try:
        file_system.get_details(body.path)
        info = file_system.move_file_or_directory(body.path, body.new_path)
        return FileMoveResponse(success=True, info=info)
    except Exception as e:
        LOGGER.error(f"Error updating file or directory: {e}")
        return FileMoveResponse(success=False, message=str(e))


@router.post("/update")
@requires("edit")
async def update_file(
    *,
    request: Request,
) -> FileUpdateResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/FileUpdateRequest"
    responses:
        200:
            description: Update a file or directory
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/FileUpdateResponse"
    """
    body = await parse_request(request, cls=FileUpdateRequest)
    try:
        file_system.get_details(body.path)
        info = file_system.update_file(body.path, body.contents)
        return FileUpdateResponse(success=True, info=info)
    except Exception as e:
        LOGGER.error(f"Error updating file or directory: {e}")
        return FileUpdateResponse(success=False, message=str(e))
