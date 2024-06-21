# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from multiprocessing import Process
from typing import TYPE_CHECKING, Optional

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
    """
    responses:
        200:
            description: Get the status of the application
            content:
                application/json:
                    schema:
                        type: object
                        properties:
                            status:
                                type: string
                            filenames:
                                type: array
                                items:
                                    type: string
                            mode:
                                type: string
                            sessions:
                                type: integer
                            version:
                                type: string
                            requirements:
                                type: array
                                items:
                                    type: string
                            node_version:
                                type: string
                            lsp_running:
                                type: boolean
    """
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
    """
    responses:
        200:
            description: Get the version of the application
            content:
                text/plain:
                    schema:
                        type: string
    """
    del request  # Unused
    return PlainTextResponse(__version__)


@router.get("/api/usage")
@requires("edit")
async def usage(request: Request) -> JSONResponse:
    """
    responses:
        200:
            description: Get the current memory and CPU usage of the application
            content:
                application/json:
                    schema:
                        type: object
                        properties:
                            memory:
                                type: object
                                properties:
                                    total:
                                        type: integer
                                    available:
                                        type: integer
                                    percent:
                                        type: number
                                    used:
                                        type: integer
                                    free:
                                        type: integer
                                required:
                                    - total
                                    - available
                                    - percent
                                    - used
                                    - free
                            server:
                                type: object
                                properties:
                                    memory:
                                        type: integer
                                required:
                                    - memory
                            kernel:
                                type: object
                                properties:
                                    memory:
                                        type: integer
                            cpu:
                                type: object
                                properties:
                                    percent:
                                        type: number
                                required:
                                    - percent
                        required:
                            - memory
                            - cpu

    """  # noqa: E501
    import psutil

    memory = psutil.virtual_memory()
    # interval=None is nonblocking; first value is meaningless but after
    # that it's useful.
    cpu = psutil.cpu_percent(interval=None)

    # Server memory (and children)
    main_process = psutil.Process()
    server_memory = main_process.memory_info().rss
    children = main_process.children(recursive=True)
    for child in children:
        try:
            server_memory += child.memory_info().rss
        except psutil.NoSuchProcess:
            pass

    # Kernel memory
    kernel_memory: Optional[int] = None
    session = AppState(request).get_current_session()
    if session and isinstance(session.kernel_manager.kernel_task, Process):
        kernel_process = psutil.Process(session.kernel_manager.kernel_task.pid)
        kernel_memory = kernel_process.memory_info().rss
        kernel_children = kernel_process.children(recursive=True)
        for child in kernel_children:
            try:
                kernel_memory += child.memory_info().rss
            except psutil.NoSuchProcess:
                pass

    return JSONResponse(
        {
            # computer memory
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
                "used": memory.used,
                "free": memory.free,
            },
            # marimo server
            "server": {
                "memory": server_memory,
            },
            # marimo kernel (for the given session)
            "kernel": {
                "memory": kernel_memory,
            },
            "cpu": {
                "percent": cpu,
            },
        }
    )
