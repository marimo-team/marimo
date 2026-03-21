# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import (
    BaseResponse,
    DocumentEventsRequest,
    SuccessResponse,
)
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

# Router for document endpoints
router = APIRouter()


@router.post("/events")
@requires("edit")
async def document_events(request: Request) -> BaseResponse:
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
                    $ref: "#/components/schemas/DocumentEventsRequest"
    responses:
        200:
            description: Apply document events
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=DocumentEventsRequest)
    session = app_state.require_current_session()

    for event in body.events:
        session.document.apply(event)

    return SuccessResponse()
