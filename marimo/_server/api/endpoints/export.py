# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires
from starlette.responses import HTMLResponse, PlainTextResponse

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.export.exporter import Exporter
from marimo._server.models.export import (
    ExportAsHTMLRequest,
    ExportAsScriptRequest,
)
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for export endpoints
router = APIRouter()


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

    html, filename = Exporter().export_as_html(
        file_manager=session.app_file_manager,
        session_view=session.session_view,
        display_config=app_state.session_manager.user_config_manager.get_config()[
            "display"
        ],
        request=body,
    )

    if body.download:
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
    else:
        headers = {}

    # Download the HTML
    return HTMLResponse(
        content=html,
        headers=headers,
    )


@router.post("/script")
@requires("edit")
async def export_as_script(
    *,
    request: Request,
) -> PlainTextResponse:
    """
    Export the notebook as a script.
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=ExportAsScriptRequest)
    session = app_state.require_current_session()

    python, filename = Exporter().export_as_script(
        file_manager=session.app_file_manager,
    )

    if body.download:
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
    else:
        headers = {}

    # Download the Script
    return PlainTextResponse(
        content=python,
        headers=headers,
    )
