# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64

from starlette.authentication import requires
from starlette.requests import Request

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
    FileUpdateRequest,
    FileUpdateResponse,
)
from marimo._server.router import APIRouter

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
    """List files and directories in a given path."""
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
    """Get details of a specific file or directory."""
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
    """Create a new file or directory."""
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
    """Delete a file or directory."""
    body = await parse_request(request, cls=FileDeleteRequest)
    try:
        file_system.get_details(body.path)
        success = file_system.delete_file_or_directory(body.path)
        return FileDeleteResponse(success=success)
    except Exception as e:
        LOGGER.error(f"Error deleting file or directory: {e}")
        return FileDeleteResponse(success=False, message=str(e))


@router.post("/update")
@requires("edit")
async def update_file_or_directory(
    *,
    request: Request,
) -> FileUpdateResponse:
    """Rename or move a file or directory."""
    body = await parse_request(request, cls=FileUpdateRequest)
    try:
        file_system.get_details(body.path)
        info = file_system.update_file_or_directory(body.path, body.new_path)
        return FileUpdateResponse(success=True, info=info)
    except Exception as e:
        LOGGER.error(f"Error updating file or directory: {e}")
        return FileUpdateResponse(success=False, message=str(e))
