# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from starlette.authentication import requires
from starlette.requests import Request

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.models.home import (
    RecentFilesResponse,
    WorkspaceFilesResponse,
)
from marimo._server.router import APIRouter

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
