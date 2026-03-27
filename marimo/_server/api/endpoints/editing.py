# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo._cli.sandbox import SandboxMode
from marimo._messaging.notification import FocusCellNotification
from marimo._server.api.deps import AppState
from marimo._server.api.utils import (
    dispatch_control_request,
    install_packages_on_server,
    notify_server_missing_packages,
    parse_request,
)
from marimo._server.models.models import (
    BaseResponse,
    CodeCompletionRequest,
    DeleteCellRequest,
    FocusCellRequest,
    FormatCellsRequest,
    FormatResponse,
    InstallPackagesRequest,
    StdinRequest,
    SuccessResponse,
    UpdateCellConfigRequest,
)
from marimo._server.router import APIRouter
from marimo._utils.formatter import DefaultFormatter

if TYPE_CHECKING:
    from starlette.requests import Request

# Router for editing endpoints
router = APIRouter()


@router.post("/code_autocomplete")
@requires("edit")
async def code_complete(request: Request) -> BaseResponse:
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
                    $ref: "#/components/schemas/CodeCompletionRequest"
    responses:
        200:
            description: Complete a code fragment
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    return await dispatch_control_request(request, cls=CodeCompletionRequest)


@router.post("/delete")
@requires("edit")
async def delete_cell(request: Request) -> BaseResponse:
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
                    $ref: "#/components/schemas/DeleteCellRequest"
    responses:
        200:
            description: Delete a cell
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    return await dispatch_control_request(request, DeleteCellRequest)


@router.post("/focus_cell")
@requires("edit")
async def focus_cell(request: Request) -> BaseResponse:
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
                    $ref: "#/components/schemas/FocusCellRequest"
    responses:
        200:
            description: Focus a cell in kiosk-mode consumers
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=FocusCellRequest)
    app_state.require_current_session().notify(
        FocusCellNotification(cell_id=body.cell_id),
        from_consumer_id=None,
    )
    return SuccessResponse()


@router.post("/format")
@requires("edit")
async def format_cell(request: Request) -> FormatResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/FormatCellsRequest"
    responses:
        200:
            description: Format code
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/FormatResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=FormatCellsRequest)
    formatter = DefaultFormatter(line_length=body.line_length)
    filename = app_state.require_current_session().app_file_manager.path
    if filename and filename.endswith((".md", ".qmd")):
        filename = f"{filename}.py"

    try:
        codes = await formatter.format(body.codes, filename)
        return FormatResponse(codes)
    except ModuleNotFoundError:
        # In multi-sandbox mode each kernel has its own venv, so installing
        # ruff into the server wouldn't help the kernel.  Just surface the
        # error without an install prompt.
        if app_state.session_manager.sandbox_mode is SandboxMode.MULTI:
            raise ModuleNotFoundError(
                "Server does not have a formatter. Please install ruff"
            ) from None
        # For single-sandbox and non-sandbox modes the server *is* the
        # formatting environment, so offer to install ruff there.
        notify_server_missing_packages(
            app_state.get_current_session(),
            app_state.get_current_session_id(),
            ["ruff"],
        )
        # Re-raise without .name so the error handler returns 500 without
        # sending a duplicate notification.
        raise ModuleNotFoundError(
            "Server does not have a formatter. Please install ruff"
        ) from None


@router.post("/set_cell_config")
@requires("edit")
async def set_cell_config(request: Request) -> BaseResponse:
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
                    $ref: "#/components/schemas/UpdateCellConfigRequest"
    responses:
        200:
            description: Set the configuration of a cell
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    return await dispatch_control_request(request, UpdateCellConfigRequest)


@router.post("/stdin")
@requires("edit")
async def stdin(request: Request) -> BaseResponse:
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
                    $ref: "#/components/schemas/StdinRequest"
    responses:
        200:
            description: Send input to the stdin stream
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=StdinRequest)
    app_state.require_current_session().put_input(body.text)

    return SuccessResponse()


@router.post("/install_missing_packages")
@requires("edit")
async def install_missing_packages(request: Request) -> BaseResponse:
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
                    $ref: "#/components/schemas/InstallPackagesRequest"
    responses:
        200:
            description: Install missing packages
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    body = await parse_request(request, cls=InstallPackagesRequest)
    cmd = body.as_command()

    if cmd.source == "server":
        # Install into the server's own Python environment (sys.executable).
        # Used when the server itself needs a package (e.g. nbformat for
        # IPYNB auto-export when running with --sandbox).
        app_state = AppState(request)
        app_state.require_current_session()
        await install_packages_on_server(cmd.manager, cmd.versions)
        return SuccessResponse()

    # Default ("kernel"): dispatch to kernel via ZeroMQ control queue.
    return await dispatch_control_request(request, cmd)
