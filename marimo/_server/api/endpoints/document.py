# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo._notebook.ops import Transaction
from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.models import (
    BaseResponse,
    NotebookDocumentTransactionRequest,
    SuccessResponse,
)
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

router = APIRouter()


@router.post("/transaction")
@requires("edit")
async def document_transaction(request: Request) -> BaseResponse:
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
                    $ref: "#/components/schemas/NotebookDocumentTransactionRequest"
    responses:
        200:
            description: Apply a document transaction
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/SuccessResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=NotebookDocumentTransactionRequest)
    session = app_state.require_current_session()

    session.document.apply(Transaction(ops=tuple(body.ops), source="frontend"))

    return SuccessResponse()
