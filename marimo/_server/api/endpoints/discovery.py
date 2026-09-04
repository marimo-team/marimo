# Copyright 2026 Marimo. All rights reserved.
"""Local discovery protocol v1 endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from starlette.responses import JSONResponse

from marimo import _loggers
from marimo._server.discovery.manager import DiscoveryManager
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.requests import Request

router = APIRouter()
LOGGER = _loggers.marimo_logger()


def _manager(request: Request) -> DiscoveryManager:
    # DiscoverySecurityMiddleware returns 404 before routing when disabled.
    return cast(DiscoveryManager, request.app.state.discovery_manager)


def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse({"message": message}, status_code=status_code)


@router.get("/catalog")
async def catalog(*, request: Request) -> object:
    """Return a complete snapshot of projects, notebooks, and sessions."""
    try:
        return await _manager(request).catalog()
    except Exception:
        LOGGER.exception("Failed to build local discovery catalog")
        return _error(500, "Failed to build catalog")
