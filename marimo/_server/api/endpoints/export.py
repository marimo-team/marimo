# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import mimetypes
import os
from typing import TYPE_CHECKING, cast

from fastapi.responses import HTMLResponse
from starlette.authentication import requires

from marimo import _loggers
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.utils import build_data_url
from marimo._runtime.virtual_file import read_virtual_file
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.export import ExportAsHTMLRequest
from marimo._server.router import APIRouter
from marimo._server.templates.templates import static_notebook_template
from marimo._utils.paths import import_files

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for expport endpoints
router = APIRouter()

# Root directory for static assets
root = os.path.realpath(str(import_files("marimo").joinpath("_static")))


@router.post("/html")
@requires("edit")
async def export_as_html(
    *,
    request: Request,
) -> HTMLResponse:
    """
    Export the notebook as HTML.
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=ExportAsHTMLRequest)
    session = app_state.require_current_session()

    index_html_file = os.path.join(root, "index.html")

    cell_ids = list(session.app_file_manager.app.cell_manager.cell_ids())
    filename = session.app_file_manager.filename
    if not filename:
        filename = "notebook.py"

    with open(index_html_file, "r") as f:  # noqa: ASYNC101
        index_html = f.read()

    files: dict[str, str] = {}
    for filename_and_length in body.files:
        if filename_and_length.startswith("/@file/"):
            filename = filename_and_length[7:]
        byte_length, basename = filename.split("-", 1)
        buffer_contents = read_virtual_file(basename, int(byte_length))
        mime_type, _ = mimetypes.guess_type(basename) or ("text/plain", None)
        files[filename_and_length] = build_data_url(
            cast(KnownMimeType, mime_type), buffer_contents
        )

    html = static_notebook_template(
        html=index_html,
        user_config=app_state.session_manager.user_config_manager.get_config(),
        server_token=app_state.server_token,
        app_config=session.app_file_manager.app.config,
        filename=session.app_file_manager.filename,
        code=session.app_file_manager.to_code(),
        cell_ids=cell_ids,
        cell_names=list(session.app_file_manager.app.cell_manager.names()),
        cell_codes=list(session.app_file_manager.app.cell_manager.codes()),
        cell_configs=list(session.app_file_manager.app.cell_manager.configs()),
        cell_outputs=session.session_view.get_cell_outputs(cell_ids),
        cell_console_outputs=session.session_view.get_cell_console_outputs(cell_ids),
        files=files,
        asset_url=body.asset_url,
    )

    basename = os.path.basename(filename)
    download_filename = f"{os.path.splitext(basename)[0]}.html"

    if body.download:
        headers = {"Content-Disposition": f"attachment; filename={download_filename}"}
    else:
        headers = {}

    # Download the HTML
    return HTMLResponse(
        content=html,
        headers=headers,
    )
