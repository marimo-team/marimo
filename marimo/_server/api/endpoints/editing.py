# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo._messaging.notification import (
    MissingPackageAlertNotification,
    UpdateCellIdsNotification,
)
from marimo._server.api.deps import AppState
from marimo._server.api.utils import dispatch_control_request, parse_request
from marimo._server.models.models import (
    BaseResponse,
    CodeCompletionRequest,
    DeleteCellRequest,
    FormatCellsRequest,
    FormatResponse,
    InstallPackagesRequest,
    StdinRequest,
    SuccessResponse,
    UpdateCellConfigRequest,
    UpdateCellIdsRequest,
)
from marimo._server.router import APIRouter
from marimo._types.ids import ConsumerId
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


@router.post("/sync/cell_ids")
@requires("edit")
async def sync_cell_ids(request: Request) -> BaseResponse:
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
                    $ref: "#/components/schemas/UpdateCellIdsRequest"
    responses:
        200:
            description: Sync cell ids
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=UpdateCellIdsRequest)
    session_id = app_state.require_current_session_id()
    app_state.require_current_session().notify(
        UpdateCellIdsNotification(cell_ids=body.cell_ids),
        from_consumer_id=ConsumerId(session_id),
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
    body = await parse_request(request, cls=FormatCellsRequest)
    formatter = DefaultFormatter(line_length=body.line_length)

    try:
        return FormatResponse(codes=await formatter.format(body.codes))
    except ModuleNotFoundError:
        from marimo._runtime.packages.utils import can_server_auto_install
        from marimo._session.utils import send_message_to_consumer

        app_state = AppState(request)
        session_id = app_state.get_current_session_id()
        session = app_state.get_current_session()
        if session_id is not None and session is not None:
            send_message_to_consumer(
                session=session,
                operation=MissingPackageAlertNotification(
                    packages=["ruff"],
                    isolated=can_server_auto_install(),
                    source="server",
                ),
                consumer_id=ConsumerId(session_id),
            )
        # Re-raise without name so the error handler returns 500 without
        # sending a second notification.
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
    from marimo._runtime.packages.package_managers import create_package_manager

    app_state = AppState(request)
    body = await parse_request(request, cls=InstallPackagesRequest)
    cmd = body.as_command()

    if cmd.source == "server":
        # Install into the server's own Python environment (sys.executable).
        # Used when the server itself needs a package (e.g. nbformat for
        # IPYNB auto-export when running with --sandbox).
        pkg_manager = create_package_manager(cmd.manager, python_exe=None)
        if not pkg_manager.is_manager_installed():
            pkg_manager.alert_not_installed()
        else:
            for pkg, version in cmd.versions.items():
                await pkg_manager.install(pkg, version=version or None)
        return SuccessResponse()

    # Default ("kernel"): dispatch to kernel via ZeroMQ control queue.
    app_state.require_current_session().put_control_request(
        cmd,
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )
    return SuccessResponse()
