# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
import pathlib
import tempfile
from typing import TYPE_CHECKING

from starlette.authentication import requires
from starlette.responses import JSONResponse

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.file_router import (
    LazyListOfFilesAppFileRouter,
    count_files,
)
from marimo._server.files.directory_scanner import DirectoryScanner
from marimo._server.models.home import (
    MarimoFile,
    OpenTutorialRequest,
    RecentFilesResponse,
    RunningNotebooksResponse,
    ShutdownSessionRequest,
    WorkspaceFilesRequest,
    WorkspaceFilesResponse,
)
from marimo._server.router import APIRouter
from marimo._session.model import ConnectionState
from marimo._tutorials import create_temp_tutorial_file  # type: ignore
from marimo._utils.paths import pretty_path

if TYPE_CHECKING:
    from starlette.requests import Request

MAX_FILES = DirectoryScanner.MAX_FILES

LOGGER = _loggers.marimo_logger()

# Router for home endpoints
router = APIRouter()


@router.post("/recent_files")
@requires("edit")
async def read_code(
    *,
    request: Request,
) -> RecentFilesResponse:
    """
    responses:
        200:
            description: Get the recent files
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/RecentFilesResponse"
    """
    app_state = AppState(request)
    # Pass the file router's directory to filter and relativize paths
    directory = None
    dir_str = app_state.session_manager.file_router.directory
    if dir_str:
        directory = pathlib.Path(dir_str)
    files = app_state.session_manager.recents.get_recents(directory)
    return RecentFilesResponse(files=files)


@router.post("/workspace_files")
@requires("edit")
async def workspace_files(
    *,
    request: Request,
) -> WorkspaceFilesResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/WorkspaceFilesRequest"
    responses:
        200:
            description: Get the files in the workspace
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/WorkspaceFilesResponse"
    """
    body = await parse_request(request, cls=WorkspaceFilesRequest)
    session_manager = AppState(request).session_manager

    # Maybe enable markdown
    root = ""
    if isinstance(session_manager.file_router, LazyListOfFilesAppFileRouter):
        # Mark stale in case new files are added
        session_manager.file_router.mark_stale()
        # Toggle markdown
        session_manager.file_router = (
            session_manager.file_router.toggle_markdown(body.include_markdown)
        )
        root = session_manager.file_router.directory

    # Run file scanning in thread pool to avoid blocking the server
    files = await asyncio.to_thread(lambda: session_manager.file_router.files)

    file_count = count_files(files)
    has_more = file_count >= MAX_FILES

    return WorkspaceFilesResponse(
        files=files,
        root=root,
        has_more=has_more,
        file_count=file_count,
    )


def _get_active_sessions(app_state: AppState) -> list[MarimoFile]:
    files: list[MarimoFile] = []
    for session_id, session in app_state.session_manager.sessions.items():
        state = session.connection_state()
        if state == ConnectionState.OPEN or state == ConnectionState.ORPHANED:
            filename = session.app_file_manager.filename
            basename = os.path.basename(filename) if filename else None
            files.append(
                MarimoFile(
                    name=(basename or "new notebook"),
                    path=(pretty_path(filename) if filename else session_id),
                    last_modified=0,
                    session_id=session_id,
                    initialization_id=session.initialization_id,
                )
            )
    # These are better in reverse
    return files[::-1]


@router.post("/running_notebooks")
@requires("edit")
async def running_notebooks(
    *,
    request: Request,
) -> RunningNotebooksResponse:
    """
    responses:
        200:
            description: Get the running files
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/RunningNotebooksResponse"
    """
    app_state = AppState(request)
    return RunningNotebooksResponse(files=_get_active_sessions(app_state))


@router.post("/shutdown_session")
@requires("edit")
async def shutdown_session(
    *,
    request: Request,
) -> RunningNotebooksResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ShutdownSessionRequest"
    responses:
        200:
            description: Shutdown the current session
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/RunningNotebooksResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=ShutdownSessionRequest)
    app_state.session_manager.close_session(body.session_id)
    return RunningNotebooksResponse(files=_get_active_sessions(app_state))


@router.post("/tutorial/open")
@requires("edit")
async def tutorial(
    *,
    request: Request,
) -> MarimoFile | JSONResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/OpenTutorialRequest"
    responses:
        200:
            description: Open a new tutorial
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/MarimoFile"
    """
    import msgspec

    # Create a new tutorial file and return the filepath
    try:
        body = await parse_request(request, cls=OpenTutorialRequest)
    except msgspec.ValidationError:
        return JSONResponse({"detail": "Tutorial not found"}, status_code=400)
    temp_dir = tempfile.TemporaryDirectory()
    path = create_temp_tutorial_file(body.tutorial_id, temp_dir)

    import atexit

    atexit.register(temp_dir.cleanup)

    # Register the temp directory with the file router so it can be accessed
    # This is needed for directory-based routers to allow temp tutorial files
    app_state = AppState(request)
    if isinstance(
        app_state.session_manager.file_router, LazyListOfFilesAppFileRouter
    ):
        app_state.session_manager.file_router.register_temp_dir(temp_dir.name)

    return MarimoFile(
        name=os.path.basename(path.absolute_name),
        path=path.absolute_name,
    )
