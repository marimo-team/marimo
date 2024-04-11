# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo._runtime.requests import (
    CompletionRequest,
    DeleteRequest,
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
from marimo._utils.formatter import BlackFormatter

if TYPE_CHECKING:
    from starlette.requests import Request

# Router for editing endpoints
router = APIRouter()


@router.post("/code_autocomplete")
@requires("edit")
async def code_complete(request: Request) -> BaseResponse:
    """Complete a code fragment."""
    app_state = AppState(request)
    body = await parse_request(request, cls=CompletionRequest)
    app_state.require_current_session().put_completion_request(body)

    return SuccessResponse()


@router.post("/delete")
@requires("edit")
async def delete_cell(request: Request) -> BaseResponse:
    """Complete a code fragment."""
    app_state = AppState(request)
    body = await parse_request(request, cls=DeleteRequest)
    app_state.require_current_session().put_control_request(body)

    return SuccessResponse()


@router.post("/format")
@requires("edit")
async def format_cell(request: Request) -> FormatResponse:
    """Complete a code fragment."""
    body = await parse_request(request, cls=FormatRequest)
    formatter = BlackFormatter(line_length=body.line_length)

    return FormatResponse(codes=formatter.format(body.codes))


@router.post("/set_cell_config")
@requires("edit")
async def set_cell_config(request: Request) -> BaseResponse:
    """Set the config for a cell."""
    app_state = AppState(request)
    body = await parse_request(request, cls=SetCellConfigRequest)
    app_state.require_current_session().put_control_request(body)

    return SuccessResponse()


@router.post("/stdin")
@requires("edit")
async def stdin(request: Request) -> BaseResponse:
    """Send input to the stdin stream."""
    app_state = AppState(request)
    body = await parse_request(request, cls=StdinRequest)
    app_state.require_current_session().put_input(body.text)

    return SuccessResponse()


# TODO(akshayka): allow in run mode when in pyodide
@router.post("/install_missing_packages")
@requires("edit")
async def install_missing_packages(request: Request) -> BaseResponse:
    """Install missing packages"""
    app_state = AppState(request)
    body = await parse_request(request, cls=InstallMissingPackagesRequest)
    app_state.require_current_session().put_control_request(body)
    return SuccessResponse()
