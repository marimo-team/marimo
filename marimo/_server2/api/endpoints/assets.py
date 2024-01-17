import json
import os
from importlib.resources import files as importlib_files

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from marimo import __version__
from marimo._config.config import get_configuration
from marimo._server import sessions
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
async def index():
    mgr = sessions.get_manager()

    title = parse_title(mgr.filename)
    user_config = get_configuration()
    app_config = mgr.app_config.asdict() if mgr.app_config is not None else {}

    index_html = os.path.join(root, "index.html")
    with open(index_html, "r") as f:
        html = f.read()
        html = html.replace("{{title}}", title)
        html = html.replace("{{user_config}}", json.dumps(user_config))
        html = html.replace("{{app_config}}", json.dumps(app_config))
        html = html.replace("{{server_token}}", mgr.server_token)
        html = html.replace("{{version}}", __version__)
        html = html.replace("{{filename}}", mgr.filename or "")
        html = html.replace(
            "{{mode}}",
            "read" if mgr.mode == sessions.SessionMode.RUN else "edit",
        )

    return html
