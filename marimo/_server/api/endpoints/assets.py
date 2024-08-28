# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import mimetypes
import os
import re
from typing import TYPE_CHECKING, Optional

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, HTMLResponse, Response
from starlette.staticfiles import StaticFiles

from marimo import _loggers
from marimo._config.manager import UserConfigManager
from marimo._runtime.virtual_file import EMPTY_VIRTUAL_FILE, read_virtual_file
from marimo._server.api.deps import AppState
from marimo._server.file_router import MarimoFileKey
from marimo._server.router import APIRouter
from marimo._server.templates.templates import (
    home_page_template,
    notebook_page_template,
)
from marimo._utils.paths import import_files

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for serving static assets
router = APIRouter()

# Root directory for static assets
root = os.path.realpath(str(import_files("marimo").joinpath("_static")))

config = UserConfigManager().get_config().get("server", {})

router.mount(
    "/assets",
    app=StaticFiles(
        directory=os.path.join(root, "assets"),
        follow_symlink=config.get("follow_symlink", False),
    ),
    name="assets",
)

FILE_QUERY_PARAM_KEY = "file"


@router.get("/")
@requires("read", redirect="auth:login_page")
async def index(request: Request) -> HTMLResponse:
    app_state = AppState(request)
    user_config = app_state.config_manager.get_config()
    index_html = os.path.join(root, "index.html")

    file_key = (
        app_state.query_params(FILE_QUERY_PARAM_KEY)
        or app_state.session_manager.file_router.get_unique_file_key()
    )

    with open(index_html, "r") as f:  # noqa: ASYNC101 ASYNC230
        html = f.read()

    if not file_key:
        # We don't know which file to use, so we need to render a homepage
        LOGGER.debug("No file key provided, serving homepage")
        html = home_page_template(
            html=html,
            base_url=app_state.base_url,
            user_config=user_config,
            server_token=app_state.skew_protection_token,
        )
    else:
        # We have a file key, so we can render the app with the file
        LOGGER.debug(f"File key provided: {file_key}")
        app_manager = app_state.session_manager.app_manager(file_key)
        app_config = app_manager.app.config

        html = notebook_page_template(
            html=html,
            base_url=app_state.base_url,
            user_config=user_config,
            server_token=app_state.skew_protection_token,
            app_config=app_config,
            filename=app_manager.filename,
            mode=app_state.mode,
        )

    return HTMLResponse(html)


# This serves the custom.css file if it was
# supplied in the app config
@router.get("/custom.css")
@requires("read")
def custom_css(request: Request) -> Response:
    app_state = AppState(request)
    file_key: Optional[MarimoFileKey] = (
        app_state.query_params(FILE_QUERY_PARAM_KEY)
        or app_state.session_manager.file_router.get_unique_file_key()
    )

    if not file_key:
        return Response("", media_type="text/css")

    app_manager = app_state.session_manager.app_manager(file_key)
    css = app_manager.read_css_file() or ""
    return Response(css, media_type="text/css")


STATIC_FILES = [
    r"(favicon\.ico)",
    r"(circle-check\.ico)",
    r"(circle-play\.ico)",
    r"(circle-x\.ico)",
    r"(manifest\.json)",
    r"(android-chrome-(192x192|512x512)\.png)",
    r"(apple-touch-icon\.png)",
    r"(logo\.png)",
]


@router.get("/@file/{filename_and_length:path}")
@requires("read")
def virtual_file(
    request: Request,
) -> Response:
    """
    parameters:
        - in: path
          name: filename_and_length
          required: true
          schema:
            type: string
          description: The filename and byte length of the virtual file
    responses:
        200:
            description: Get a virtual file
            content:
                application/octet-stream:
                    schema:
                        type: string
        404:
            description: Invalid virtual file request
        404:
            description: Invalid byte length in virtual file request
    """
    filename_and_length = request.path_params["filename_and_length"]

    LOGGER.debug("Getting virtual file: %s", filename_and_length)
    if filename_and_length == EMPTY_VIRTUAL_FILE.filename:
        return Response(content=b"", media_type="application/octet-stream")
    if "-" not in filename_and_length:
        raise HTTPException(
            status_code=404,
            detail="Invalid virtual file request",
        )

    byte_length, filename = filename_and_length.split("-", 1)
    if not byte_length.isdigit():
        raise HTTPException(
            status_code=404,
            detail="Invalid byte length in virtual file request",
        )

    buffer_contents = read_virtual_file(filename, int(byte_length))
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
