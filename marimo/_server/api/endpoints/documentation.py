# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

# from starlette.authentication import requires
from starlette.requests import Request

from marimo import _loggers
from marimo._server.router import APIRouter
from marimo._snippets.snippets import Snippets, read_snippets

LOGGER = _loggers.marimo_logger()

# Router for documentation
router = APIRouter()


@router.get("/snippets")
# @router.post("/snippets")
# @requires("edit")
async def load_snippets(
    request: Request,
) -> Snippets:
    return read_snippets()
