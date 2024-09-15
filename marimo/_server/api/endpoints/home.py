# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING, List

from starlette.authentication import requires
from starlette.responses import JSONResponse

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.file_router import LazyListOfFilesAppFileRouter
from marimo._server.model import ConnectionState
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
from marimo._tutorials import create_temp_tutorial_file
from marimo._utils.paths import pretty_path

if TYPE_CHECKING:
    from starlette.requests import Request

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
    files = app_state.session_manager.recents.get_recents()
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

    files = session_manager.file_router.files
    return WorkspaceFilesResponse(files=files, root=root)


def _get_active_sessions(app_state: AppState) -> List[MarimoFile]:
    files: List[MarimoFile] = []
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
    # Create a new tutorial file and return the filepath
    try:
        body = await parse_request(request, cls=OpenTutorialRequest)
    except ValueError:
        return JSONResponse({"detail": "Tutorial not found"}, status_code=400)
    temp_dir = tempfile.TemporaryDirectory()
    path = create_temp_tutorial_file(body.tutorial_id, temp_dir)

    import atexit

    atexit.register(temp_dir.cleanup)

    return MarimoFile(
        name=os.path.basename(path.absolute_name),
        path=path.absolute_name,
    )
