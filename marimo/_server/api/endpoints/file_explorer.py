# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_multipart_request, parse_request
from marimo._server.files.os_file_system import OSFileSystem
from marimo._server.models.files import (
    FileCopyRequest,
    FileCopyResponse,
    FileCreateMultipartRequest,
    FileCreateResponse,
    FileDeleteRequest,
    FileDeleteResponse,
    FileDetailsRequest,
    FileDetailsResponse,
    FileListRequest,
    FileListResponse,
    FileMoveRequest,
    FileMoveResponse,
    FileOpenRequest,
    FileSearchRequest,
    FileSearchResponse,
    FileUpdateRequest,
    FileUpdateResponse,
)
from marimo._server.models.models import (
    BaseResponse,
    ErrorResponse,
    SuccessResponse,
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
    app_state = AppState(request)
    body = await parse_request(request, cls=FileListRequest)
    # Use workspace's directory as default, fall back to cwd
    directory = app_state.session_manager.workspace.directory
    root = body.path or directory or file_system.get_root()
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
            multipart/form-data:
                schema:
                    $ref: "#/components/schemas/FileCreateMultipartRequest"
    responses:
        200:
            description: Create a new file or directory
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/FileCreateResponse"
    """
    try:
        parsed = await parse_multipart_request(
            request, FileCreateMultipartRequest
        )
        info = file_system.create_file_or_directory(
            parsed.body.path,
            parsed.body.type,
            parsed.body.name,
            parsed.files.get("file"),
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
        # TODO: Refactor this side-effect based validation to a dedicated validation.
        file_system.get_details(body.path)
        success = file_system.delete_file_or_directory(body.path)
        return FileDeleteResponse(success=success)
    except Exception as e:
        LOGGER.error(f"Error deleting file or directory: {e}")
        return FileDeleteResponse(success=False, message=str(e))


@router.post("/copy")
@requires("edit")
async def copy_file_or_directory(
    *,
    request: Request,
) -> FileCopyResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/FileCopyRequest"
    responses:
        200:
            description: Copy a file or directory
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/FileCopyResponse"
    """
    body = await parse_request(request, cls=FileCopyRequest)
    try:
        # TODO: Refactor this side-effect based validation to a dedicated validation.
        file_system.get_details(body.path)
        info = file_system.copy_file_or_directory(body.path, body.new_path)
        return FileCopyResponse(success=True, info=info)
    except Exception as e:
        LOGGER.error(f"Error copying file or directory: {e}")
        return FileCopyResponse(success=False, message=str(e))


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
        # TODO: Refactor this side-effect based validation to a dedicated validation.
        file_system.get_details(body.path)
        info = file_system.move_file_or_directory(body.path, body.new_path)
        return FileMoveResponse(success=True, info=info)
    except Exception as e:
        LOGGER.error(f"Error moving file or directory: {e}")
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
    app_state = AppState(request)
    body = await parse_request(request, cls=FileUpdateRequest)
    try:
        # TODO: Refactor this side-effect based validation to a dedicated validation.
        file_system.get_details(body.path)
        info = file_system.update_file(body.path, body.contents)

        # Handle marimo notebook reload if there's an active session
        session_manager = app_state.session_manager
        await session_manager.trigger_file_change(body.path)

        return FileUpdateResponse(success=True, info=info)
    except Exception as e:
        LOGGER.error(f"Error updating file or directory: {e}")
        return FileUpdateResponse(success=False, message=str(e))


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
                    $ref: "#/components/schemas/FileOpenRequest"
    responses:
        200:
            description: Open a file in the system editor
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/BaseResponse"
    """
    body = await parse_request(request, cls=FileOpenRequest)
    try:
        # TODO: Refactor this side-effect based validation to a dedicated validation.
        file_system.get_details(body.path)
        success = file_system.open_in_editor(body.path, body.line_number)
        return SuccessResponse(success=success)
    except Exception as e:
        LOGGER.error(f"Error opening file: {e}")
        return ErrorResponse(success=False, message=str(e))


@router.post("/search")
@requires("edit")
async def search_files(
    *,
    request: Request,
) -> FileSearchResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/FileSearchRequest"
    responses:
        200:
            description: Search for files and directories matching a query
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/FileSearchResponse"
    """
    body = await parse_request(request, cls=FileSearchRequest)
    files = file_system.search(
        query=body.query,
        path=body.path,
        include_directories=body.include_directories,
        include_files=body.include_files,
        depth=body.depth,
        limit=body.limit,
    )
    return FileSearchResponse(
        files=files, query=body.query, total_found=len(files)
    )
