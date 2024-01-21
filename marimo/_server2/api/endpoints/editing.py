# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.cell import CellId_t
from marimo._config.utils import LOGGER
from marimo._runtime import requests
from marimo._server2.api.deps import get_current_session
from marimo._server2.api.utils import parse_request
from marimo._server2.models.models import (
    BaseResponse,
    CodeCompleteRequest,
    DeleteCellRequest,
    FormatRequest,
    FormatResponse,
    StdinRequest,
    SuccessResponse,
)
from marimo._server2.router import APIRouter
from starlette.requests import Request

# Router for editing endpoints
router = APIRouter()


@router.post("/code_autocomplete")
async def code_complete(request: Request) -> BaseResponse:
    """Complete a code fragment."""
    body = await parse_request(request, cls=CodeCompleteRequest)
    get_current_session(request).control_queue.put(
        requests.CompletionRequest(
            completion_id=body.id,
            document=body.document,
            cell_id=body.cell_id,
        )
    )

    return SuccessResponse()


@router.post("/delete")
async def delete_cell(request: Request) -> BaseResponse:
    """Complete a code fragment."""
    body = await parse_request(request, cls=DeleteCellRequest)
    get_current_session(request).control_queue.put(
        requests.DeleteRequest(cell_id=body.cell_id)
    )

    return SuccessResponse()


@router.post("/format")
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
async def set_cell_config(request: Request) -> BaseResponse:
    """Set the config for a cell."""
    body = await parse_request(request, cls=requests.SetCellConfigRequest)
    request.app.session().control_queue.put(
        requests.SetCellConfigRequest(configs=body.configs)
    )

    return SuccessResponse()


@router.post("/stdin")
async def stdin(request: Request) -> BaseResponse:
    """Send input to the stdin stream."""
    body = await parse_request(request, cls=StdinRequest)
    request.app.session().input_queue.put(body.text)

    return SuccessResponse()
