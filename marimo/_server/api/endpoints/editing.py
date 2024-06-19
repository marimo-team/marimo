# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo._messaging.ops import UpdateCellIdsRequest
from marimo._runtime.requests import (
    CodeCompletionRequest,
    DeleteCellRequest,
    InstallMissingPackagesRequest,
    SetCellConfigRequest,
)
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import (
    BaseResponse,
    FormatRequest,
    FormatResponse,
    StdinRequest,
    SuccessResponse,
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
    app_state = AppState(request)
    body = await parse_request(request, cls=CodeCompletionRequest)
    app_state.require_current_session().put_completion_request(body)

    return SuccessResponse()


@router.post("/delete")
@requires("edit")
async def delete_cell(request: Request) -> BaseResponse:
    """
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
    app_state = AppState(request)
    body = await parse_request(request, cls=DeleteCellRequest)
    app_state.require_current_session().put_control_request(body)

    return SuccessResponse()


@router.post("/sync/cell_ids")
@requires("edit")
async def sync_cell_ids(request: Request) -> BaseResponse:
    """
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
    app_state.require_current_session().write_operation(body)
    return SuccessResponse()


@router.post("/format")
@requires("edit")
async def format_cell(request: Request) -> FormatResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/FormatRequest"
    responses:
        200:
            description: Format code
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/FormatResponse"
    """
    body = await parse_request(request, cls=FormatRequest)
    formatter = DefaultFormatter(line_length=body.line_length)

    return FormatResponse(codes=formatter.format(body.codes))


@router.post("/set_cell_config")
@requires("edit")
async def set_cell_config(request: Request) -> BaseResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/SetCellConfigRequest"
    responses:
        200:
            description: Set the configuration of a cell
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=SetCellConfigRequest)
    app_state.require_current_session().put_control_request(body)

    return SuccessResponse()


@router.post("/stdin")
@requires("edit")
async def stdin(request: Request) -> BaseResponse:
    """
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
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/InstallMissingPackagesRequest"
    responses:
        200:
            description: Install missing packages
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=InstallMissingPackagesRequest)
    app_state.require_current_session().put_control_request(body)
    return SuccessResponse()
