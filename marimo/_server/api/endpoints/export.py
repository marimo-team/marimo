# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlencode

from starlette.authentication import requires
from starlette.background import BackgroundTask
from starlette.exceptions import HTTPException
from starlette.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
)

from marimo import _loggers
from marimo._convert.common.filename import (
    get_download_filename,
    make_download_headers,
)
from marimo._convert.markdown import convert_from_ir_to_markdown
from marimo._convert.markdown.flavor import (
    markdown_output_filename,
    normalize_markdown_flavor,
)
from marimo._convert.script import convert_from_ir_to_script
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.msgspec_encoder import asdict
from marimo._server.api.deps import AppState
from marimo._server.api.utils import (
    get_code_mode_credentials,
    notify_server_missing_packages,
    parse_request,
)
from marimo._server.export.exporter import AutoExporter, Exporter
from marimo._server.models.export import (
    ExportAsHTMLRequest,
    ExportAsIPYNBRequest,
    ExportAsMarkdownRequest,
    ExportAsPDFRequest,
    ExportAsScriptRequest,
    UpdateCellOutputsRequest,
)
from marimo._server.models.models import SuccessResponse
from marimo._server.router import APIRouter
from marimo._utils.http import HTTPStatus

if TYPE_CHECKING:
    from starlette.requests import Request

    from marimo._schemas.serialization import NotebookSerializationV1
    from marimo._types.ids import SessionId

LOGGER = _loggers.marimo_logger()

# Router for export endpoints
router = APIRouter()

auto_exporter = AutoExporter()


def build_slides_pdf_live_url(
    *,
    server_url: str,
    session_id: SessionId,
    file_key: str,
    auth_token: str | None,
    include_inputs: bool,
) -> str:
    """Build the kiosk + print-pdf URL for live slides PDF capture.

    `file` is required — without it the edit server serves the home page
    instead of the notebook (so reveal never mounts).
    """
    params: dict[str, str] = {
        "file": file_key,
        "session_id": str(session_id),
        "kiosk": "true",
        "show-chrome": "false",
        "print-pdf": "true",
        "view-as": "slides",
    }
    if auth_token is not None:
        params["access_token"] = auth_token
    if not include_inputs:
        params["show-code"] = "false"
    separator = "&" if "?" in server_url else "?"
    return f"{server_url}{separator}{urlencode(params)}"


def _export_markdown(
    notebook: NotebookSerializationV1, filename: str | None
) -> tuple[str, str]:
    export_filename = filename or notebook.filename
    markdown_flavor = normalize_markdown_flavor(
        None, filename=export_filename or "notebook.md"
    )
    markdown = convert_from_ir_to_markdown(
        notebook, filename=export_filename, flavor=markdown_flavor
    )
    return (
        markdown,
        markdown_output_filename(export_filename, markdown_flavor),
    )


@router.post("/html")
@requires("read")
async def export_as_html(
    *,
    request: Request,
) -> HTMLResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
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

    # Check if the file is named
    if not session.app_file_manager.is_notebook_named:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="File must have a name before exporting",
        )

    # Only include the code if allowed (edit mode or include_code=True)
    if not app_state.session_manager.should_send_code_to_frontend():
        body.include_code = False

    resolved_config = session.config_manager.get_config()
    html, filename = Exporter().export_as_html(
        app=session.app_file_manager.app,
        filename=session.app_file_manager.filename,
        session_view=session.session_view,
        display_config=resolved_config["display"],
        sharing_config=resolved_config.get("sharing"),
        request=body,
    )

    if body.download:
        headers = make_download_headers(filename)
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
) -> JSONResponse | PlainTextResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
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

    # Reload the file manager to get the latest state
    session.app_file_manager.reload()
    session_view = session.session_view

    if not session.app_file_manager.is_notebook_named:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="File must have a name before exporting",
        )

    # If we have already exported to HTML, don't do it again
    if not session_view.needs_export("html"):
        LOGGER.debug("Already auto-exported to HTML")
        return PlainTextResponse(status_code=HTTPStatus.NOT_MODIFIED)

    # If session_view is empty (no outputs), don't export
    if session_view.is_empty():
        LOGGER.info("No outputs to export")
        return PlainTextResponse(status_code=HTTPStatus.NOT_MODIFIED)

    async def _background_export() -> None:
        html, _filename = Exporter().export_as_html(
            app=session.app_file_manager.app,
            filename=session.app_file_manager.filename,
            session_view=session_view,
            display_config=session.config_manager.get_config()["display"],
            request=body,
        )

        # Save the HTML file to disk, at `.marimo/<filename>.html`
        await auto_exporter.save_html(
            filename=session.app_file_manager.filename,
            html=html,
        )
        session_view.mark_auto_export_html()

    return JSONResponse(
        content=asdict(SuccessResponse()),
        background=BackgroundTask(_background_export),
    )


@router.post("/script")
@requires("edit")
async def export_as_script(
    *,
    request: Request,
) -> PlainTextResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
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

    python = convert_from_ir_to_script(session.app_file_manager.app.to_ir())
    filename = get_download_filename(
        session.app_file_manager.filename, "script.py"
    )

    if body.download:
        headers = make_download_headers(filename)
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
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
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

    markdown, download_filename = _export_markdown(
        app_file_manager.app.to_ir(), app_file_manager.filename
    )

    if body.download:
        headers = make_download_headers(download_filename)
    else:
        headers = {}

    # Download the Markdown
    return PlainTextResponse(
        content=markdown,
        headers=headers,
    )


@router.post("/ipynb")
@requires("edit")
async def export_as_ipynb(
    *,
    request: Request,
) -> PlainTextResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ExportAsIPYNBRequest"
    responses:
        200:
            description: Export the notebook as IPYNB
            content:
                text/plain:
                    schema:
                        type: string
        400:
            description: File must be saved before downloading
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=ExportAsIPYNBRequest)
    session = app_state.require_current_session()

    if not session.app_file_manager.is_notebook_named:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="File must have a name before exporting",
        )

    ipynb = Exporter().export_as_ipynb(
        app=session.app_file_manager.app,
        sort_mode="top-down",
        session_view=session.session_view,
    )

    if body.download:
        filename = get_download_filename(
            session.app_file_manager.filename, "ipynb"
        )
        headers = make_download_headers(filename)
    else:
        headers = {}

    # Download the IPYNB
    return PlainTextResponse(
        content=ipynb,
        headers=headers,
    )


@router.post("/auto_export/markdown")
@requires("edit")
async def auto_export_as_markdown(
    *,
    request: Request,
) -> JSONResponse | PlainTextResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
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

    if not session.app_file_manager.is_notebook_named:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="File must have a name before exporting",
        )

    # If we have already exported to Markdown, don't do it again
    if not session_view.needs_export("md"):
        LOGGER.debug("Already auto-exported to Markdown")
        return PlainTextResponse(status_code=HTTPStatus.NOT_MODIFIED)

    async def _background_export() -> None:
        # Reload the file manager to get the latest state
        session.app_file_manager.reload()

        markdown = convert_from_ir_to_markdown(
            session.app_file_manager.app.to_ir()
        )

        # Save the Markdown file to disk, at `.marimo/<filename>.md`
        await auto_exporter.save_md(
            filename=session.app_file_manager.filename,
            markdown=markdown,
        )
        session_view.mark_auto_export_md()

    return JSONResponse(
        content=asdict(SuccessResponse()),
        background=BackgroundTask(_background_export),
    )


@router.post("/auto_export/ipynb")
@requires("edit")
async def auto_export_as_ipynb(
    *,
    request: Request,
) -> JSONResponse | PlainTextResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ExportAsIPYNBRequest"
    responses:
        200:
            description: Export the notebook as IPYNB
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

    if not session.app_file_manager.is_notebook_named:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="File must have a name before exporting",
        )

    # If we have already exported to IPYNB, don't do it again
    if not session_view.needs_export("ipynb"):
        LOGGER.debug("Already auto-exported to IPYNB")
        return PlainTextResponse(status_code=HTTPStatus.NOT_MODIFIED)

    # Check nbformat before scheduling background task.  Alert at most once
    # per session so the notification doesn't keep popping up on every save.
    if not DependencyManager.nbformat.has():
        LOGGER.warning("Cannot snapshot to IPYNB: nbformat not installed")
        if "nbformat" not in session_view.notified_server_packages:
            notify_server_missing_packages(
                session, app_state.get_current_session_id(), ["nbformat"]
            )
            session_view.notified_server_packages.add("nbformat")
        session_view.mark_auto_export_ipynb()
        return PlainTextResponse(status_code=HTTPStatus.NOT_MODIFIED)

    async def _background_export() -> None:
        # Reload the file manager to get the latest state
        session.app_file_manager.reload()

        ipynb = Exporter().export_as_ipynb(
            app=session.app_file_manager.app,
            sort_mode="top-down",
            session_view=session_view,
        )

        # Save the IPYNB file to disk, at `.marimo/<filename>.ipynb`
        await auto_exporter.save_ipynb(
            filename=session.app_file_manager.filename,
            ipynb=ipynb,
        )
        session_view.mark_auto_export_ipynb()

    return JSONResponse(
        content=asdict(SuccessResponse()),
        background=BackgroundTask(_background_export),
    )


@router.post("/pdf")
@requires("edit")
async def export_as_pdf(*, request: Request) -> Response:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/ExportAsPDFRequest"
    responses:
        200:
            description: Export the notebook as a PDF
            content:
                application/pdf:
                    schema:
                        type: string
                        format: binary
        400:
            description: File must be saved before downloading
        500:
            description: Export failed or dependencies missing
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=ExportAsPDFRequest)
    session = app_state.require_current_session()

    if not session.app_file_manager.is_notebook_named:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="File must have a name before exporting",
        )

    exporter = Exporter()
    if body.preset == "slides":
        server_url, auth_token = get_code_mode_credentials(app_state, request)
        # Prefer the session file key (same value the browser puts in ?file=).
        file_key = (
            session.initialization_id
            or session.app_file_manager.filename
            or ""
        )
        if not file_key:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="File must have a name before exporting slides PDF",
            )
        live_page_url = build_slides_pdf_live_url(
            server_url=server_url,
            session_id=app_state.require_current_session_id(),
            file_key=file_key,
            auth_token=auth_token if app_state.enable_auth else None,
            include_inputs=body.include_inputs,
        )
        pdf_data = await exporter.export_as_slides_pdf(
            app=session.app_file_manager.app,
            session_view=session.session_view,
            include_inputs=body.include_inputs,
            live_page_url=live_page_url,
        )
    else:
        pdf_data = exporter.export_as_pdf(
            app=session.app_file_manager.app,
            session_view=session.session_view,
            webpdf=body.webpdf,
            include_inputs=body.include_inputs,
        )
    if pdf_data is None:
        raise HTTPException(
            status_code=HTTPStatus.SERVER_ERROR, detail="Failed to export PDF"
        )
    filename = get_download_filename(session.app_file_manager.filename, "pdf")
    headers = make_download_headers(filename)

    return Response(
        content=pdf_data, media_type="application/pdf", headers=headers
    )


@router.post("/update_cell_outputs")
@requires("edit")
async def update_cell_outputs(
    *, request: Request
) -> JSONResponse | PlainTextResponse:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/UpdateCellOutputsRequest"
    responses:
        200:
            description: Update the cell outputs
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
        400:
            description: File must be saved before downloading
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=UpdateCellOutputsRequest)
    session = app_state.require_current_session()
    session.session_view.update_cell_outputs(body.cell_ids_to_output)

    return JSONResponse(content=asdict(SuccessResponse()))
