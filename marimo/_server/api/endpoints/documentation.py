# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo import _loggers
from marimo._server.api.deps import AppState
from marimo._server.router import APIRouter
from marimo._snippets.snippets import Snippets, read_snippets

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for documentation
router = APIRouter()

# Cache snippets once per server instance
_SNIPPETS: list[Snippets] = []


@router.get("/snippets")
@requires("edit")
async def load_snippets(
    *,
    request: Request,
) -> Snippets:
    """
    parameters:
        - in: header
          name: Marimo-Session-Id
          schema:
            type: string
          required: true
    responses:
        200:
            description: Load the snippets for the documentation page
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/Snippets"
    """
    app_state = AppState(request)
    config = app_state.require_current_session().config_manager.get_config()
    if not _SNIPPETS:
        _SNIPPETS.append(await read_snippets(config))
    return _SNIPPETS[0]
