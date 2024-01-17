import json
import os
import re
from importlib.resources import files as importlib_files

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from marimo import __version__
from marimo._config.config import get_configuration
from marimo._server.model import SessionMode
from marimo._server2.api.deps import SessionManagerStateDep
from marimo._server2.api.utils import parse_title

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
        state.app_config.asdict() if state.app_config is not None else {}
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
]


# Catch all for serving static files
@router.get("/{path:path}")
async def serve_static(path: str) -> FileResponse:
    if any(re.match(pattern, path) for pattern in STATIC_FILES):
        return FileResponse(os.path.join(root, path))

    raise HTTPException(status_code=404, detail="Not Found")
