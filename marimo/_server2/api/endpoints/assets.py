# Copyright 2024 Marimo. All rights reserved.
import json
import mimetypes
import os
import re
from http import HTTPStatus
from importlib.resources import files as importlib_files
from multiprocessing import shared_memory

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from marimo import __version__, _loggers
from marimo._config.config import get_configuration
from marimo._runtime.virtual_file import EMPTY_VIRTUAL_FILE
from marimo._server.model import SessionMode
from marimo._server2.api.deps import SessionManagerStateDep
from marimo._server2.api.utils import parse_title

LOGGER = _loggers.marimo_logger()

# Router for serving static assets
router = APIRouter()

# Root directory for static assets
root = os.path.realpath(str(importlib_files("marimo").joinpath("_static")))

router.mount(
    "/assets",
    StaticFiles(directory=os.path.join(root, "assets")),
    name="assets",
)


@router.get("/")
async def index(state: SessionManagerStateDep):
    title = parse_title(state.filename)
    user_config = get_configuration()
    app_config = (
        state.app_config.dict() if state.app_config is not None else {}
    )

    index_html = os.path.join(root, "index.html")
    with open(index_html, "r") as f:
        html = f.read()
        html = html.replace("{{ title }}", title)
        html = html.replace("{{ user_config }}", json.dumps(user_config))
        html = html.replace("{{ app_config }}", json.dumps(app_config))
        html = html.replace("{{ server_token }}", state.server_token)
        html = html.replace("{{ version }}", json.dumps(__version__))
        html = html.replace("{{ filename }}", state.filename or "")
        html = html.replace(
            "{{ mode }}",
            json.dumps("read" if state.mode == SessionMode.RUN else "edit"),
        )

    return HTMLResponse(html)


STATIC_FILES = [
    r"(favicon\.ico)",
    r"(manifest\.json)",
    r"(android-chrome-(192x192|512x512)\.png)",
    r"(apple-touch-icon\.png)",
    r"(assets\/.*)",
]


@router.get("/@file/{filename_and_length:path}")
def virtual_file(
    *,
    filename_and_length: str,
) -> Response:
    """Handler for virtual files."""

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
async def serve_static(path: str) -> FileResponse:
    if any(re.match(pattern, path) for pattern in STATIC_FILES):
        return FileResponse(os.path.join(root, path))

    raise HTTPException(status_code=404, detail="Not Found")
