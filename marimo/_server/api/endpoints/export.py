# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, PlainTextResponse

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.api.status import HTTPStatus
from marimo._server.api.utils import parse_request
from marimo._server.export.exporter import AutoExporter, Exporter
from marimo._server.model import SessionMode
from marimo._server.models.export import (
    ExportAsHTMLRequest,
    ExportAsMarkdownRequest,
    ExportAsScriptRequest,
)
from marimo._server.models.models import SuccessResponse
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for export endpoints
router = APIRouter()


@router.post("/html")
@requires("read")
async def export_as_html(
    *,
    request: Request,
) -> HTMLResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ExportAsHTMLRequest"
    responses:
        200:
            description: Export the notebook as HTML
            content:
                text/html:
                    schema:
                        type: string
        400:
            description: File must be saved before downloading
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=ExportAsHTMLRequest)
    session = app_state.require_current_session()

    # Only include the code and console if we are in edit mode
    if app_state.mode != SessionMode.EDIT:
        body.include_code = False

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


@router.post("/auto_export/html")
@requires("edit")
async def auto_export_as_html(
    *,
    request: Request,
) -> SuccessResponse | PlainTextResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ExportAsHTMLRequest"
    responses:
        200:
            description: Export the notebook as HTML
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
        400:
            description: File must be saved before downloading
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=ExportAsHTMLRequest)
    session = app_state.require_current_session()
    session_view = session.session_view

    # If we have already exported to HTML, don't do it again
    if session_view.has_auto_exported_html:
        LOGGER.debug("Already auto-exported to HTML")
        return PlainTextResponse(status_code=HTTPStatus.NOT_MODIFIED)

    # Reload the file manager to get the latest state
    session.app_file_manager.reload()

    html, _filename = Exporter().export_as_html(
        file_manager=session.app_file_manager,
        session_view=session_view,
        display_config=app_state.session_manager.user_config_manager.get_config()[
            "display"
        ],
        request=body,
    )

    # Save the HTML file to disk, at `.marimo/<filename>.html`
    AutoExporter().save_html(
        file_manager=session.app_file_manager,
        html=html,
    )
    session_view.mark_auto_export_html()

    return SuccessResponse()


@router.post("/script")
@requires("edit")
async def export_as_script(
    *,
    request: Request,
) -> PlainTextResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ExportAsScriptRequest"
    responses:
        200:
            description: Export the notebook as a script
            content:
                text/plain:
                    schema:
                        type: string
        400:
            description: File must be saved before downloading
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


@router.post("/markdown")
@requires("edit")
async def export_as_markdown(
    *,
    request: Request,
) -> PlainTextResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ExportAsMarkdownRequest"
    responses:
        200:
            description: Export the notebook as a markdown
            content:
                text/plain:
                    schema:
                        type: string
        400:
            description: File must be saved before downloading
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=ExportAsMarkdownRequest)
    app_file_manager = app_state.require_current_session().app_file_manager
    # Reload the file manager to get the latest state
    app_file_manager.reload()

    if not app_file_manager.path:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="File must be saved before downloading",
        )

    markdown, filename = Exporter().export_as_md(
        file_manager=app_file_manager,
    )

    if body.download:
        headers = {"Content-Disposition": f"attachment; filename={filename}"}
    else:
        headers = {}

    # Download the Markdown
    return PlainTextResponse(
        content=markdown,
        headers=headers,
    )


@router.post("/auto_export/markdown")
@requires("edit")
async def auto_export_as_markdown(
    *,
    request: Request,
) -> SuccessResponse | PlainTextResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ExportAsMarkdownRequest"
    responses:
        200:
            description: Export the notebook as a markdown
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
        400:
            description: File must be saved before downloading
    """
    app_state = AppState(request)
    session = app_state.require_current_session()
    session_view = session.session_view

    # If we have already exported to Markdown, don't do it again
    if session_view.has_auto_exported_md:
        LOGGER.debug("Already auto-exported to Markdown")
        return PlainTextResponse(status_code=HTTPStatus.NOT_MODIFIED)

    # Reload the file manager to get the latest state
    session.app_file_manager.reload()

    markdown, _filename = Exporter().export_as_md(
        file_manager=session.app_file_manager,
    )

    # Save the Markdown file to disk, at `.marimo/<filename>.md`
    AutoExporter().save_md(
        file_manager=session.app_file_manager,
        markdown=markdown,
    )
    session_view.mark_auto_export_md()

    return SuccessResponse()
