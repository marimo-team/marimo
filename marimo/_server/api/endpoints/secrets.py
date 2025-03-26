# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires

from marimo import _loggers
from marimo._secrets.secrets import get_secret_keys
from marimo._server.models.secrets import (
    ListSecretKeysResponse,
)
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()

# Router for secrets endpoints
router = APIRouter()


@router.post("/keys")
@requires("edit")
async def list_keys(request: Request) -> ListSecretKeysResponse:
    """
    responses:
        200:
            description: Preview a column in a dataset
            content:
                application/json:
                    schema:
                        $ref: "#/components/schemas/ListSecretKeysResponse"
    """
    del request
    return ListSecretKeysResponse(keys=get_secret_keys())
