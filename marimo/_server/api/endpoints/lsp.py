# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_request
from marimo._server.models.lsp import (
    LspHealthResponse,
    LspRestartRequest,
    LspRestartResponse,
)
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

# Router for LSP endpoints
router = APIRouter()


@router.get("/health")
@requires("edit")
async def lsp_health(request: Request) -> LspHealthResponse:
    """
    responses:
        200:
            description: Get health status of all LSP servers
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/LspHealthResponse"
    """
    app_state = AppState(request)
    return await app_state.session_manager.lsp_server.get_health()


@router.post("/restart")
@requires("edit")
async def lsp_restart(request: Request) -> LspRestartResponse:
    """
    requestBody:
        content:
            application/json:
                schema:
                    $ref: "#/components/schemas/LspRestartRequest"
    responses:
        200:
            description: Restart LSP servers
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/LspRestartResponse"
    """
    app_state = AppState(request)
    body = await parse_request(request, cls=LspRestartRequest)
    return await app_state.session_manager.lsp_server.restart(
        server_ids=body.server_ids
    )
