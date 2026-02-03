# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
import pathlib
import tempfile
from typing import TYPE_CHECKING

from starlette.authentication import requires
from starlette.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.file_router import (
    LazyListOfFilesAppFileRouter,
    ListOfFilesAppFileRouter,
    count_files,
    flatten_files,
)
from marimo._server.files.directory_scanner import DirectoryScanner
from marimo._server.files.path_validator import PathValidator
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
from marimo._session.model import ConnectionState, SessionMode
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
@requires("read")
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
    app_state = AppState(request)
    session_manager = app_state.session_manager

    if session_manager.mode == SessionMode.RUN:
        from marimo._metadata.opengraph import (
            OpenGraphContext,
            resolve_opengraph_metadata,
        )
        from marimo._server.models.files import FileInfo

        base_url = app_state.base_url
        mode = session_manager.mode.value

        def get_files_with_metadata() -> list[FileInfo]:
            files = session_manager.file_router.files
            marimo_files = [
                file for file in flatten_files(files) if file.is_marimo_file
            ]
            result: list[FileInfo] = []
            for file in marimo_files:
                resolved_path = session_manager.file_router.resolve_file_path(
                    file.path
                )
                opengraph = None
                if resolved_path is not None:
                    # User-defined OpenGraph generators receive this context for dynamic metadata
                    opengraph = resolve_opengraph_metadata(
                        resolved_path,
                        context=OpenGraphContext(
                            filepath=resolved_path,
                            file_key=file.path,
                            base_url=base_url,
                            mode=mode,
                        ),
                    )
                result.append(
                    FileInfo(
                        id=file.id,
                        path=file.path,
                        name=file.name,
                        is_directory=file.is_directory,
                        is_marimo_file=file.is_marimo_file,
                        last_modified=file.last_modified,
                        children=file.children,
                        opengraph=opengraph,
                    )
                )
            return result

        marimo_files = await asyncio.to_thread(get_files_with_metadata)
        file_count = len(marimo_files)
        has_more = file_count >= MAX_FILES
        return WorkspaceFilesResponse(
            files=marimo_files,
            root=session_manager.file_router.directory or "",
            has_more=has_more,
            file_count=file_count,
        )

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


@router.get("/thumbnail", include_in_schema=False)
@requires("read")
def thumbnail(
    *,
    request: Request,
) -> Response:
    """Serve a notebook thumbnail for gallery/OpenGraph use."""
    from pathlib import Path

    from marimo._metadata.opengraph import (
        DEFAULT_OPENGRAPH_PLACEHOLDER_IMAGE_GENERATOR,
        OpenGraphContext,
        is_https_url,
        resolve_opengraph_metadata,
    )
    from marimo._utils.http import HTTPException, HTTPStatus
    from marimo._utils.paths import normalize_path

    app_state = AppState(request)
    file_key = (
        app_state.query_params("file")
        or app_state.session_manager.file_router.get_unique_file_key()
    )
    if not file_key:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="File not found"
        )

    notebook_path = app_state.session_manager.file_router.resolve_file_path(
        file_key
    )
    if notebook_path is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="File not found"
        )

    notebook_dir = normalize_path(Path(notebook_path)).parent
    marimo_dir = notebook_dir / "__marimo__"

    # User-defined OpenGraph generators receive this context (file key, base URL, mode)
    # so they can compute metadata dynamically for gallery cards, social previews, and other modes.
    opengraph = resolve_opengraph_metadata(
        notebook_path,
        context=OpenGraphContext(
            filepath=notebook_path,
            file_key=file_key,
            base_url=app_state.base_url,
            mode=app_state.mode.value,
        ),
    )
    title = opengraph.title or "marimo"
    image = opengraph.image

    validator = PathValidator()
    if image:
        if is_https_url(image):
            return RedirectResponse(
                url=image,
                status_code=307,
                headers={"Cache-Control": "max-age=3600"},
            )

        rel_path = Path(image)
        if not rel_path.is_absolute():
            file_path = normalize_path(notebook_dir / rel_path)
            # Only allow serving from the notebook's __marimo__ directory.
            try:
                if file_path.is_file():
                    validator.validate_inside_directory(marimo_dir, file_path)
                    return FileResponse(
                        file_path,
                        headers={"Cache-Control": "max-age=3600"},
                    )
            except HTTPException:
                # Treat invalid paths as a miss; fall back to placeholder.
                pass

    placeholder = DEFAULT_OPENGRAPH_PLACEHOLDER_IMAGE_GENERATOR(title)
    return Response(
        content=placeholder.content,
        media_type=placeholder.media_type,
        # Avoid caching placeholders so newly-generated screenshots show up
        # immediately on refresh.
        headers={"Cache-Control": "no-store"},
    )


def _get_active_sessions(app_state: AppState) -> list[MarimoFile]:
    """Get list of active sessions with prettified paths."""
    # Get directory from file router for path relativization
    base_dir = app_state.session_manager.file_router.directory

    files: list[MarimoFile] = []
    for session_id, session in app_state.session_manager.sessions.items():
        state = session.connection_state()
        if state == ConnectionState.OPEN or state == ConnectionState.ORPHANED:
            filename = session.app_file_manager.filename
            basename = os.path.basename(filename) if filename else None
            files.append(
                MarimoFile(
                    name=(basename or "new notebook"),
                    path=pretty_path(filename, base_dir)
                    if filename
                    else session_id,
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
    elif isinstance(
        app_state.session_manager.file_router, ListOfFilesAppFileRouter
    ):
        app_state.session_manager.file_router.register_allowed_file(
            path.absolute_name
        )

    return MarimoFile(
        name=os.path.basename(path.absolute_name),
        path=path.absolute_name,
    )
