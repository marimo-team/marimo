# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import List

from starlette.authentication import requires
from starlette.requests import Request

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.model import ConnectionState
from marimo._server.models.home import (
    MarimoFile,
    RecentFilesResponse,
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
async def rename_file(
    *,
    request: Request,
) -> WorkspaceFilesResponse:
    """Get the files in the workspace."""
    app_state = AppState(request)
    files = app_state.session_manager.file_router.files
    return WorkspaceFilesResponse(files=files)


@router.post("/running_notebooks")
@requires("edit")
async def running_notebooks(
    *,
    request: Request,
) -> WorkspaceFilesResponse:
    """Get the running files."""
    app_state = AppState(request)
    files: List[MarimoFile] = []
    for session_id, session in app_state.session_manager.sessions.items():
        if session.connection_state() == ConnectionState.OPEN:
            filename = session.app_file_manager.filename
            basename = os.path.basename(filename) if filename else None
            files.append(
                MarimoFile(
                    name=(basename or "new notebook"),
                    path=(pretty_path(filename) if filename else session_id),
                    last_modified=0,
                )
            )
    return WorkspaceFilesResponse(files=files)
