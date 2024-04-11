# Copyright 2024 Marimo. All rights reserved.
import json
import mimetypes
import os
import re
from http import HTTPStatus
from multiprocessing import shared_memory

from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, Response
from starlette.staticfiles import StaticFiles

from marimo import __version__, _loggers
from marimo._runtime.virtual_file import EMPTY_VIRTUAL_FILE
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_title
from marimo._server.model import SessionMode
from marimo._server.router import APIRouter
from marimo._utils.paths import import_files

LOGGER = _loggers.marimo_logger()

# Router for serving static assets
router = APIRouter()

# Root directory for static assets
root = os.path.realpath(str(import_files("marimo").joinpath("_static")))

router.mount(
    "/assets",
    app=StaticFiles(directory=os.path.join(root, "assets")),
    name="assets",
)

FILE_QUERY_PARAM_KEY = "file"


@router.get("/")
async def index(request: Request) -> HTMLResponse:
    app_state = AppState(request)
    user_config = app_state.config_manager.get_config()
    index_html = os.path.join(root, "index.html")

    file_key = (
        app_state.query_params(FILE_QUERY_PARAM_KEY)
        or app_state.session_manager.file_router.get_unique_file_key()
    )

    with open(index_html, "r") as f:
        html = f.read()

    # Shared configuration
    html = html.replace("{{ base_url }}", app_state.base_url)
    html = html.replace("{{ user_config }}", json.dumps(user_config))
    html = html.replace("{{ server_token }}", app_state.server_token)
    html = html.replace("{{ version }}", __version__)

    if not file_key:
        LOGGER.debug("No file key provided, serving homepage")
        # We don't know which file to use, so we need to render a homepage
        html = html.replace("{{ title }}", "marimo")
        html = html.replace("{{ app_config }}", json.dumps({}))
        html = html.replace("{{ filename }}", "")
        html = html.replace("{{ mode }}", "home")
    else:
        LOGGER.debug(f"File key provided: {file_key}")
        # We have a file key, so we can render the app with the file
        app_manager = app_state.session_manager.app_manager(file_key)
        app_config = app_manager.app.config.asdict()

        html = html.replace("{{ title }}", parse_title(app_manager.filename))
        html = html.replace("{{ app_config }}", json.dumps(app_config))
        html = html.replace("{{ filename }}", app_manager.filename or "")
        html = html.replace(
            "{{ mode }}",
            "read" if app_state.mode == SessionMode.RUN else "edit",
        )

    return HTMLResponse(html)


STATIC_FILES = [
    r"(favicon\.ico)",
    r"(manifest\.json)",
    r"(android-chrome-(192x192|512x512)\.png)",
    r"(apple-touch-icon\.png)",
    r"(logo\.png)",
]


@router.get("/@file/{filename_and_length:path}")
def virtual_file(
    request: Request,
) -> Response:
    """Handler for virtual files."""
    filename_and_length = request.path_params["filename_and_length"]

    LOGGER.debug("Getting virtual file: %s", filename_and_length)
    if filename_and_length == EMPTY_VIRTUAL_FILE.filename:
        return Response(content=b"", media_type="application/octet-stream")

    byte_length, filename = filename_and_length.split("-", 1)
    key = filename
    shm = None
    try:
        # NB: this can't be collapsed into a one-liner!
        # doing it in one line yields a 'released memoryview ...'
        # because shared_memory has built in ref-tracking + GC
        shm = shared_memory.SharedMemory(name=key)
        buffer_contents = bytes(shm.buf)[: int(byte_length)]
    except FileNotFoundError as err:
        LOGGER.debug(
            "Error retrieving shared memory for virtual file: %s", err
        )
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            detail="File not found",
        ) from err
    finally:
        if shm is not None:
            shm.close()
    mimetype, _ = mimetypes.guess_type(filename)
    return Response(
        content=buffer_contents,
        media_type=mimetype,
        headers={"Cache-Control": "max-age=86400"},
    )


# Catch all for serving static files
@router.get("/{path:path}")
async def serve_static(request: Request) -> FileResponse:
    path = request.path_params["path"]
    if any(re.match(pattern, path) for pattern in STATIC_FILES):
        return FileResponse(os.path.join(root, path))

    raise HTTPException(status_code=404, detail="Not Found")
