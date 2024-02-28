# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

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
    return file_system.get_details(body.path)


@router.post("/create")
@requires("edit")
async def create_file_or_directory(
    *,
    request: Request,
) -> FileCreateResponse:
    """Create a new file or directory."""
    body = await parse_request(request, cls=FileCreateRequest)
    success = file_system.create_file_or_directory(
        body.path, body.type, body.name
    )
    return FileCreateResponse(success=success)


@router.post("/delete")
@requires("edit")
async def delete_file_or_directory(
    *,
    request: Request,
) -> FileDeleteResponse:
    """Delete a file or directory."""
    body = await parse_request(request, cls=FileDeleteRequest)
    success = file_system.delete_file_or_directory(body.path)
    return FileDeleteResponse(success=success)


@router.post("/update")
@requires("edit")
async def update_file_or_directory(
    *,
    request: Request,
) -> FileUpdateResponse:
    """Rename or move a file or directory."""
    body = await parse_request(request, cls=FileUpdateRequest)
    success = file_system.update_file_or_directory(body.path, body.new_path)
    return FileUpdateResponse(success=success)
