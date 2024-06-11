# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo import _loggers
from marimo._runtime.requests import PreviewDatasetColumnRequest
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import BaseResponse, SuccessResponse
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for data source endpoints
router = APIRouter()


@router.post("/preview_column")
@requires("edit")
async def preview_column(
    request: Request,
) -> BaseResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/PreviewDatasetColumnRequest"
    responses:
        200:
            description: Preview a column in a dataset
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, PreviewDatasetColumnRequest)
    app_state.require_current_session().put_control_request(body)
    return SuccessResponse()
