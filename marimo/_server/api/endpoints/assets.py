# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import TYPE_CHECKING

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, HTMLResponse, Response
from starlette.staticfiles import StaticFiles

from marimo import _loggers
from marimo._config.manager import get_default_config_manager
from marimo._output.utils import uri_decode_component, uri_encode_component
from marimo._runtime.virtual_file import EMPTY_VIRTUAL_FILE, read_virtual_file
from marimo._server.api.deps import AppState
from marimo._server.router import APIRouter
from marimo._server.templates.templates import (
    home_page_template,
    inject_script,
    notebook_page_template,
)
from marimo._utils.paths import import_files

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for serving static assets
router = APIRouter()

# Root directory for static assets
root = Path(import_files("marimo").joinpath("_static")).resolve()

server_config = (
    get_default_config_manager(current_path=None)
    .get_config()
    .get("server", {})
)

assets_dir = root / "assets"
follow_symlinks = server_config.get("follow_symlink", False)

if not follow_symlinks and assets_dir.is_symlink():
    LOGGER.error(
        "Assets directory is a symlink but follow_symlink=false.\n"
        "To fix this:\n"
        "1. Run 'marimo config show' to see your current config\n"
        "2. Add 'follow_symlink = true' under the [server] section in your config\n"
        "3. Restart marimo\n\n"
        "Example config:\n"
        "[server]\n"
        "follow_symlink = true"
    )

try:
    router.mount(
        "/assets",
        app=StaticFiles(
            directory=assets_dir,
            follow_symlink=follow_symlinks,
        ),
        name="assets",
    )
except RuntimeError:
    LOGGER.error("Static files not found, skipping mount")

FILE_QUERY_PARAM_KEY = "file"


@router.get("/")
@requires("read", redirect="auth:login_page")
async def index(request: Request) -> HTMLResponse:
    app_state = AppState(request)
    index_html = root / "index.html"

    file_key = (
        app_state.query_params(FILE_QUERY_PARAM_KEY)
        or app_state.session_manager.file_router.get_unique_file_key()
    )

    html = index_html.read_text()

    if not file_key:
        # We don't know which file to use, so we need to render a homepage
        LOGGER.debug("No file key provided, serving homepage")
        html = home_page_template(
            html=html,
            base_url=app_state.base_url,
            user_config=app_state.config_manager.get_user_config(),
            config_overrides=app_state.config_manager.get_config_overrides(),
            server_token=app_state.skew_protection_token,
        )
    else:
        config_manager = app_state.config_manager_at_file(file_key)

        # We have a file key, so we can render the app with the file
        LOGGER.debug(f"File key provided: {file_key}")
        app_manager = app_state.session_manager.app_manager(file_key)
        app_config = app_manager.app.config

        html = notebook_page_template(
            html=html,
            base_url=app_state.base_url,
            user_config=config_manager.get_user_config(),
            config_overrides=config_manager.get_config_overrides(),
            server_token=app_state.skew_protection_token,
            app_config=app_config,
            filename=app_manager.filename,
            mode=app_state.mode,
        )

        # Inject service worker registration with the notebook ID
        html = _inject_service_worker(html, file_key)

    return HTMLResponse(html)


def _inject_service_worker(html: str, file_key: str) -> str:
    return inject_script(
        html,
        # Register service worker with the notebook ID
        # Potentially update the service worker and send the notebook ID again.
        f"""
            if ('serviceWorker' in navigator) {{
                const notebookId = '{uri_encode_component(file_key)}';
                navigator.serviceWorker.register('./public-files-sw.js?v=2')
                    .then(registration => {{
                        registration.active.postMessage({{ notebookId }});
                    }})
                    .catch(error => {{
                        console.error('Error registering service worker:', error);
                    }});
                navigator.serviceWorker.ready
                    .then(registration => {{
                        registration.update().then(() => registration.active.postMessage({{ notebookId }}));
                    }})
                    .catch(error => {{
                        console.error('Error updating service worker:', error);
                    }});
            }}
            """,
    )


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


@router.get("/public-files-sw.js")
async def public_files_service_worker(request: Request) -> Response:
    """
    Service worker that adds the notebook ID to the request headers.
    """
    del request
    return Response(
        content="""
        let notebookIdPromise = new Promise((resolve) => {
            self.addEventListener('message', (event) => {
                if (event.data.notebookId) {
                    resolve(event.data.notebookId);
                }
            });
        });

        self.addEventListener('fetch', function(event) {
            if (event.request.url.includes('/public/')) {
                event.respondWith(
                    notebookIdPromise.then(notebookId => {
                        return fetch(event.request.url, {
                            headers: {
                                'X-Notebook-Id': notebookId
                            }
                        });
                    })
                );
            }
        });
        """,
        media_type="application/javascript",
    )


@router.get("/public/{filepath:path}")
@requires("read")
async def serve_public_file(request: Request) -> Response:
    """Serve files from the notebook's directory under /public/"""
    app_state = AppState(request)
    filepath = str(request.path_params["filepath"])
    # Get notebook ID from header
    notebook_id = request.headers.get("X-Notebook-Id")
    if notebook_id:
        # Decode notebook ID
        notebook_id = uri_decode_component(notebook_id)
        app_manager = app_state.session_manager.app_manager(notebook_id)
        if app_manager.filename:
            notebook_dir = Path(app_manager.filename).parent
        else:
            notebook_dir = Path.cwd()
        public_dir = notebook_dir / "public"
        file_path = (public_dir / filepath).resolve()

        # Security check: ensure file is inside public directory
        try:
            file_path.relative_to(public_dir.resolve())
        except ValueError:
            return Response(status_code=403, content="Access denied")

        if file_path.is_file() and not file_path.is_symlink():
            return FileResponse(file_path)

    raise HTTPException(status_code=404, detail="File not found")


# Catch all for serving static files
@router.get("/{path:path}")
async def serve_static(request: Request) -> FileResponse:
    path = str(request.path_params["path"])
    if any(re.match(pattern, path) for pattern in STATIC_FILES):
        return FileResponse(root / path)

    raise HTTPException(status_code=404, detail="Not Found")
