# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.authentication import requires
from starlette.responses import JSONResponse, PlainTextResponse

from marimo import __version__, _loggers
from marimo._server.api.deps import AppState
from marimo._server.router import APIRouter
from marimo._utils.health import get_node_version, get_required_modules_list

if TYPE_CHECKING:
    from starlette.requests import Request

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
@requires("edit")
async def status(request: Request) -> JSONResponse:
    app_state = AppState(request)
    files = [
        session.app_file_manager.filename or "__new__"
        for session in app_state.session_manager.sessions.values()
    ]
    return JSONResponse(
        {
            "status": "healthy",
            "filenames": files,
            "mode": app_state.mode,
            "sessions": len(app_state.session_manager.sessions),
            "version": __version__,
            "requirements": get_required_modules_list(),
            "node_version": get_node_version(),
            "lsp_running": app_state.session_manager.lsp_server.is_running(),
        }
    )


@router.get("/api/version")
async def version(request: Request) -> PlainTextResponse:
    del request  # Unused
    return PlainTextResponse(__version__)


@router.get("/api/usage")
@requires("edit")
async def usage(request: Request) -> JSONResponse:
    del request
    import psutil

    memory = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=1)

    return JSONResponse(
        {
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
                "used": memory.used,
                "free": memory.free,
            },
            "cpu": {
                "percent": cpu,
            },
        }
    )
