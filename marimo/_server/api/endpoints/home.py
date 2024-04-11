# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import List

from starlette.authentication import requires
from starlette.requests import Request

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.model import ConnectionState
from marimo._server.models.home import (
    MarimoFile,
    RecentFilesResponse,
    ShutdownSessionRequest,
    WorkspaceFilesResponse,
)
from marimo._server.router import APIRouter
from marimo._utils.paths import pretty_path

LOGGER = _loggers.marimo_logger()

# Router for home endpoints
router = APIRouter()


@router.post("/recent_files")
@requires("edit")
async def read_code(
    *,
    request: Request,
) -> RecentFilesResponse:
    """Get the recent files."""
    app_state = AppState(request)
    files = app_state.session_manager.recents.get_recents()
    return RecentFilesResponse(files=files)


@router.post("/workspace_files")
@requires("edit")
async def workspace_files(
    *,
    request: Request,
) -> WorkspaceFilesResponse:
    """Get the files in the workspace."""
    app_state = AppState(request)
    files = app_state.session_manager.file_router.files
    return WorkspaceFilesResponse(files=files)


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
                )
            )
    return files


@router.post("/running_notebooks")
@requires("edit")
async def running_notebooks(
    *,
    request: Request,
) -> WorkspaceFilesResponse:
    """Get the running files."""
    app_state = AppState(request)
    return WorkspaceFilesResponse(files=_get_active_sessions(app_state))


@router.post("/shutdown_session")
@requires("edit")
async def shutdown_session(
    *,
    request: Request,
) -> WorkspaceFilesResponse:
    """Shutdown the current session."""
    app_state = AppState(request)
    body = await parse_request(request, cls=ShutdownSessionRequest)
    app_state.session_manager.close_session(body.session_id)
    return WorkspaceFilesResponse(files=_get_active_sessions(app_state))
