# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from fastapi import APIRouter

from marimo._ast.cell import CellId_t
from marimo._config.utils import LOGGER
from marimo._runtime import requests
from marimo._server2.api.deps import SessionDep
from marimo._server2.models.models import (
    BaseResponse,
    CodeCompleteRequest,
    DeleteCellRequest,
    FormatRequest,
    FormatResponse,
    StdinRequest,
    SuccessResponse,
)

# Router for editing endpoints
router = APIRouter()


@router.post("/code_autocomplete", response_model=BaseResponse)
def code_complete(
    *,
    request: CodeCompleteRequest,
    session: SessionDep,
) -> BaseResponse:
    """Complete a code fragment."""
    session.control_queue.put(
        requests.CompletionRequest(
            completion_id=request.id,
            document=request.document,
            cell_id=request.cell_id,
        )
    )

    return SuccessResponse()


@router.post("/delete", response_model=BaseResponse)
def delete_cell(
    *,
    request: DeleteCellRequest,
    session: SessionDep,
) -> BaseResponse:
    """Complete a code fragment."""
    session.control_queue.put(requests.DeleteRequest(cell_id=request.cell_id))

    return SuccessResponse()


@router.post("/format", response_model=FormatResponse)
def format_cell(
    *,
    request: FormatRequest,
) -> FormatResponse:
    """Complete a code fragment."""
    try:
        import black
    except ModuleNotFoundError:
        LOGGER.warn(
            "To enable code formatting, install black (pip install black)"
        )
        return FormatResponse(codes={})

    formatted_codes: dict[CellId_t, str] = {}
    for key, code in request.codes.items():
        try:
            mode = black.Mode(line_length=request.line_length)  # type: ignore
            formatted = black.format_str(code, mode=mode)
            formatted_codes[key] = formatted.strip()
        except Exception:
            formatted_codes[key] = code
    return FormatResponse(codes=formatted_codes)


@router.post("/set_cell_config", response_model=BaseResponse)
def set_cell_config(
    *,
    request: requests.SetCellConfigRequest,
    session: SessionDep,
) -> BaseResponse:
    """Set the config for a cell."""
    session.control_queue.put(requests.SetCellConfigRequest(request.configs))

    return SuccessResponse()


@router.post("/stdin", response_model=BaseResponse)
def stdin(
    *,
    request: StdinRequest,
    session: SessionDep,
) -> BaseResponse:
    """Send input to the stdin stream."""
    session.input_queue.put(request.text)

    return SuccessResponse()
