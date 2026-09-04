# Copyright 2026 Marimo. All rights reserved.
"""Local discovery protocol v1 endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from starlette.responses import JSONResponse, StreamingResponse

from marimo import _loggers
from marimo._server.discovery.manager import DiscoveryManager
from marimo._server.router import APIRouter
from marimo._server.sse import SSE_HEADERS

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


@router.get("/catalog/watch")
async def watch_catalog(*, request: Request) -> StreamingResponse:
    """Notify subscribers when they should refetch the complete catalog."""
    return StreamingResponse(
        _manager(request).watch(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/notebooks/{notebook_id}/open")
async def open_notebook(*, request: Request) -> object:
    """Return a publisher-defined launch URI for a notebook."""
    notebook_id = request.path_params["notebook_id"]
    try:
        return await _manager(request).open_notebook(notebook_id)
    except KeyError:
        return _error(404, "Notebook not found")
    except RuntimeError as e:
        return _error(409, str(e))
    except Exception:
        LOGGER.exception("Failed to open a locally discovered notebook")
        return _error(500, "Failed to open notebook")
