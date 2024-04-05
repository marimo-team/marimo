# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from functools import lru_cache

from starlette.requests import Request

from marimo import _loggers
from marimo._server.router import APIRouter
from marimo._snippets.snippets import Snippets, read_snippets

LOGGER = _loggers.marimo_logger()

# Router for documentation
router = APIRouter()


# Cache the snippets
@lru_cache(1)
def _read_snippets_once() -> Snippets:
    return read_snippets()


@router.get("/snippets")
async def load_snippets(
    _request: Request,
) -> Snippets:
    return _read_snippets_once()
