# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

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
    make_export_headers,
)
from marimo._convert.script import UnsupportedAsyncCodeError
from marimo._export.dependencies import get_missing_export_packages
from marimo._export.exporter import (
    AutoExporter,
    Exporter,
    export_markdown,
    export_script,
    render_pdf,
)
from marimo._export.requests import (
    HTMLExportRequest,
    IPYNBExportRequest,
    MarkdownExportRequest,
    PDFExportRequest,
    ScriptExportRequest,
)
from marimo._export.serialization import serialize_notebook_snapshot
from marimo._messaging.msgspec_encoder import asdict
from marimo._schemas.export import (
    ExportAsHTMLRequest,
    ExportAsIPYNBRequest,
    ExportAsMarkdownRequest,
    ExportAsPDFRequest,
    ExportAsScriptRequest,
    ExportAvailabilityResponse,
    ExportFormatAvailability,
    UpdateCellOutputsRequest,
    to_html_export_options,
    to_ipynb_export_options,
    to_markdown_export_options,
    to_pdf_export_options,
)
from marimo._schemas.export_options import (
    SERVER_EXPORT_FORMATS,
    IPYNBExportOptions,
    MarkdownExportOptions,
)
from marimo._server.api.deps import AppState
from marimo._server.api.utils import (
    notify_server_missing_packages,
    parse_request,
)
from marimo._server.models.models import SuccessResponse
from marimo._server.router import APIRouter
from marimo._utils.http import HTTPStatus

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for export endpoints
router = APIRouter()

auto_exporter = AutoExporter()


@router.get("/availability")
@requires("read")
async def get_export_availability(
    *,
    request: Request,
) -> ExportAvailabilityResponse:
    """
    responses:
        200:
            description: Dependency readiness for server-backed exports
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/ExportAvailabilityResponse"
    """
    del request
    formats: list[ExportFormatAvailability] = []
    for export_format in SERVER_EXPORT_FORMATS:
        missing_packages = get_missing_export_packages(export_format)
        formats.append(
            ExportFormatAvailability(
                format=export_format,
                dependencies_available=not missing_packages,
                missing_packages=missing_packages,
            )
        )
    return ExportAvailabilityResponse(source="server", formats=formats)


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
    app = session.app_file_manager.app
    html, filename = Exporter().export_as_html(
        HTMLExportRequest(
            filename=session.app_file_manager.filename,
            app_code=app.to_py(),
            app_config=app.config,
            snapshot=serialize_notebook_snapshot(
                app,
                session.session_view,
                drop_virtual_file_outputs=False,
                include_model_notifications=True,
            ),
            display_config=resolved_config["display"],
            options=to_html_export_options(body),
            sharing_config=resolved_config.get("sharing"),
        )
    )

    # Download the HTML
    return HTMLResponse(
        content=html,
        headers=make_export_headers(filename, download=body.download),
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
        app = session.app_file_manager.app
        html, _filename = Exporter().export_as_html(
            HTMLExportRequest(
                filename=session.app_file_manager.filename,
                app_code=app.to_py(),
                app_config=app.config,
                snapshot=serialize_notebook_snapshot(
                    app,
                    session_view,
                    drop_virtual_file_outputs=False,
                    include_model_notifications=True,
                ),
                display_config=session.config_manager.get_config()["display"],
                options=to_html_export_options(body),
            )
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
            description: Invalid export request
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=ExportAsScriptRequest)
    session = app_state.require_current_session()

    try:
        result = export_script(
            ScriptExportRequest(
                notebook=replace(
                    session.app_file_manager.app.to_ir(),
                    filename=session.app_file_manager.filename,
                ),
            )
        )
    except UnsupportedAsyncCodeError as error:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=str(error),
        ) from error

    # Download the Script
    return PlainTextResponse(
        content=result.text,
        headers=make_export_headers(
            result.download_filename,
            download=body.download,
        ),
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

    if not app_file_manager.path:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="File must be saved before downloading",
        )

    result = export_markdown(
        MarkdownExportRequest(
            notebook=app_file_manager.app.to_ir(),
            options=to_markdown_export_options(
                body,
                filename=app_file_manager.filename,
                source_filename=app_file_manager.filename,
            ),
        )
    )

    # Download the Markdown
    return PlainTextResponse(
        content=result.text,
        headers=make_export_headers(
            result.download_filename, download=body.download
        ),
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
        IPYNBExportRequest(
            app=session.app_file_manager.app,
            options=to_ipynb_export_options(body),
            session_view=session.session_view
            if body.include_outputs
            else None,
        )
    )

    filename = get_download_filename(
        session.app_file_manager.filename, "ipynb"
    )

    # Download the IPYNB
    return PlainTextResponse(
        content=ipynb,
        headers=make_export_headers(filename, download=body.download),
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
                    $ref: "#/components/schemas/AutoExportAsMarkdownRequest"
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

        result = export_markdown(
            MarkdownExportRequest(
                notebook=session.app_file_manager.app.to_ir(),
                options=MarkdownExportOptions(),
            )
        )

        # Save the Markdown file to disk, at `.marimo/<filename>.md`
        await auto_exporter.save_md(
            filename=session.app_file_manager.filename,
            markdown=result.text,
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
                    $ref: "#/components/schemas/AutoExportAsIPYNBRequest"
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

    # Check server dependencies before scheduling the background task.
    missing_packages = get_missing_export_packages("ipynb")
    if missing_packages:
        LOGGER.warning(
            "Cannot snapshot to IPYNB: %s not installed",
            ", ".join(missing_packages),
        )
        unnotified_packages = [
            package
            for package in missing_packages
            if package not in session_view.notified_server_packages
        ]
        if unnotified_packages:
            notify_server_missing_packages(
                session,
                app_state.get_current_session_id(),
                unnotified_packages,
            )
            session_view.notified_server_packages.update(unnotified_packages)
        session_view.mark_auto_export_ipynb()
        return PlainTextResponse(status_code=HTTPStatus.NOT_MODIFIED)

    async def _background_export() -> None:
        # Reload the file manager to get the latest state
        session.app_file_manager.reload()

        ipynb = Exporter().export_as_ipynb(
            IPYNBExportRequest(
                app=session.app_file_manager.app,
                options=IPYNBExportOptions(sort_mode="top-down"),
                session_view=session_view,
            )
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

    export_request = PDFExportRequest(
        app=session.app_file_manager.app,
        session_view=session.session_view if body.include_outputs else None,
        options=to_pdf_export_options(body),
    )
    pdf_data = await render_pdf(export_request)
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
