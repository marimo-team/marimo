# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse

from marimo import __version__, _loggers
from marimo._server.api.deps import AppState
from marimo._server.router import APIRouter

LOGGER = _loggers.marimo_logger()

# Router for health/status endpoints
router = APIRouter()


async def health_check(request: Request) -> JSONResponse:
    del request  # Unused
    return JSONResponse({"status": "healthy"})


# Multiple health endpoints to make it easier on the consumer
router.add_route("/health", health_check, methods=["GET"])
router.add_route("/healthz", health_check, methods=["GET"])


@router.get("/api/status")
async def status(request: Request) -> JSONResponse:
    app_state = AppState(request)
    return JSONResponse(
        {
            "status": "healthy",
            "filename": app_state.filename,
            "mode": app_state.mode,
            "sessions": len(app_state.session_manager.sessions),
            "version": __version__,
            "lsp_running": app_state.session_manager.lsp_server.is_running(),
        }
    )
