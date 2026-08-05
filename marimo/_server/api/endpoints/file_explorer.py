# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse

from marimo import _loggers
from marimo._convert.common.filename import make_download_headers
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_multipart_request, parse_request
from marimo._server.files.os_file_system import (
    OSFileSystem,
    UploadTooLargeError,
)
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
from marimo._utils.http import HTTPException as MarimoHTTPException

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
    if body.max_bytes is not None and body.max_bytes < 0:
        raise HTTPException(
            status_code=400,
            detail="maxBytes must be non-negative",
        )
    # Only bound the read when the caller asks for it. The file preview is
    # the sole caller that sets a limit; other consumers read in full.
    return file_system.get_details(body.path, max_bytes=body.max_bytes)


@router.get("/download")
@requires("edit")
def download_file(
    *,
    request: Request,
) -> FileResponse:
    """
    parameters:
        - in: query
          name: path
          required: true
          schema:
            type: string
          description: Path of the file to download
    responses:
        200:
            description: Stream the file as an attachment
            content:
                application/octet-stream:
                    schema:
                        type: string
                        format: binary
        400:
            description: Path is missing or is a directory
        403:
            description: File downloads are disabled
        404:
            description: File not found
    """
    app_state = AppState(request)
    server_config = app_state.config_manager.get_config().get("server", {})
    # This endpoint serves raw file bytes, so its errors raise marimo's
    # HTTPException, whose status code reaches the client unchanged. A Starlette
    # 403 is globally converted to a 401 to prompt re-authentication; a
    # downloads-disabled policy cannot be satisfied by re-auth, so it stays 403.
    if server_config.get("disable_file_downloads", False):
        raise MarimoHTTPException(
            status_code=403, detail="File downloads are disabled"
        )

    path = app_state.query_params("path")
    if not path:
        raise MarimoHTTPException(status_code=400, detail="Missing path")
    file_path = Path(path)
    if file_path.is_dir():
        raise MarimoHTTPException(
            status_code=400, detail="Cannot download a directory"
        )
    if not file_path.is_file():
        raise MarimoHTTPException(status_code=404, detail="File not found")

    media_type = (
        mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    )
    return FileResponse(
        file_path,
        media_type=media_type,
        headers={
            **make_download_headers(file_path.name),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


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
        async with parse_multipart_request(
            request, FileCreateMultipartRequest
        ) as parsed:
            upload = parsed.files.get("file")
            # Directories and the default-template notebook take the
            # in-memory path; only real file content streams.
            if upload is not None and parsed.body.type in ("file", "notebook"):
                info = await file_system.stream_create_file(
                    parsed.body.path, parsed.body.name, upload
                )
            else:
                info = file_system.create_file_or_directory(
                    parsed.body.path, parsed.body.type, parsed.body.name, None
                )
        return FileCreateResponse(success=True, info=info)
    except UploadTooLargeError as e:
        LOGGER.warning(f"Rejected oversize upload: {e}")
        raise HTTPException(status_code=413, detail=str(e)) from e
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
        file_system.get_info(body.path)
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
        file_system.get_info(body.path)
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
        file_system.get_info(body.path)
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
        file_system.get_info(body.path)
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
        file_system.get_info(body.path)
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
