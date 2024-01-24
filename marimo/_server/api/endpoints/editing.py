# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from starlette.authentication import requires
from starlette.requests import Request

from marimo._ast.cell import CellId_t
from marimo._config.utils import LOGGER
from marimo._runtime import requests
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import (
    BaseResponse,
    CodeCompleteRequest,
    DeleteCellRequest,
    FormatRequest,
    FormatResponse,
    SetCellConfigRequest,
    StdinRequest,
    SuccessResponse,
)
from marimo._server.router import APIRouter

# Router for editing endpoints
router = APIRouter()


@router.post("/code_autocomplete")
@requires("edit")
async def code_complete(request: Request) -> BaseResponse:
    """Complete a code fragment."""
    app_state = AppState(request)
    body = await parse_request(request, cls=CodeCompleteRequest)
    app_state.require_current_session().put_request(
        requests.CompletionRequest(
            completion_id=body.id,
            document=body.document,
            cell_id=body.cell_id,
        )
    )

    return SuccessResponse()


@router.post("/delete")
@requires("edit")
async def delete_cell(request: Request) -> BaseResponse:
    """Complete a code fragment."""
    app_state = AppState(request)
    body = await parse_request(request, cls=DeleteCellRequest)
    app_state.require_current_session().put_request(
        requests.DeleteRequest(cell_id=body.cell_id)
    )

    return SuccessResponse()


@router.post("/format")
@requires("edit")
async def format_cell(request: Request) -> FormatResponse:
    """Complete a code fragment."""
    try:
        import black
    except ModuleNotFoundError:
        LOGGER.warn(
            "To enable code formatting, install black (pip install black)"
        )
        return FormatResponse(codes={})

    body = await parse_request(request, cls=FormatRequest)
    formatted_codes: dict[CellId_t, str] = {}
    for key, code in body.codes.items():
        try:
            mode = black.Mode(line_length=body.line_length)  # type: ignore
            formatted = black.format_str(code, mode=mode)
            formatted_codes[key] = formatted.strip()
        except Exception:
            formatted_codes[key] = code
    return FormatResponse(codes=formatted_codes)


@router.post("/set_cell_config")
@requires("edit")
async def set_cell_config(request: Request) -> BaseResponse:
    """Set the config for a cell."""
    app_state = AppState(request)
    body = await parse_request(request, cls=SetCellConfigRequest)
    app_state.require_current_session().put_request(
        requests.SetCellConfigRequest(configs=body.configs)
    )

    return SuccessResponse()


@router.post("/stdin")
@requires("edit")
async def stdin(request: Request) -> BaseResponse:
    """Send input to the stdin stream."""
    app_state = AppState(request)
    body = await parse_request(request, cls=StdinRequest)
    app_state.require_current_session().put_input(body.text)

    return SuccessResponse()
