# Copyright 2026 Marimo. All rights reserved.
"""Local discovery protocol v1 endpoints."""

from __future__ import annotations

from contextlib import aclosing
from typing import TYPE_CHECKING, cast

import msgspec
from starlette.responses import JSONResponse, Response, StreamingResponse

from marimo import _loggers
from marimo._runtime.commands import HTTPRequest
from marimo._server.api.utils import parse_request
from marimo._server.discovery.manager import DiscoveryManager
from marimo._server.discovery.models import ExecuteRequest
from marimo._server.router import APIRouter
from marimo._server.scratchpad import stream_scratchpad_code
from marimo._server.sse import SSE_HEADERS
from marimo._session.types import KernelState
from marimo._types.ids import SessionId

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.types import Receive, Scope, Send

    from marimo._session.types import Session

router = APIRouter()
LOGGER = _loggers.marimo_logger()


def _manager(request: Request) -> DiscoveryManager:
    # DiscoverySecurityMiddleware returns 404 before routing when disabled.
    return cast(DiscoveryManager, request.app.state.discovery_manager)


def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse({"message": message}, status_code=status_code)


class _ExecutionResponse(Response):
    """Own screenshot credentials through streaming, including disconnects."""

    def __init__(
        self,
        *,
        manager: DiscoveryManager,
        session: Session,
        request: Request,
        code: str,
        http_request: HTTPRequest,
    ) -> None:
        super().__init__()
        self._manager = manager
        self._session = session
        self._request = request
        self._code = code
        self._http_request = http_request

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        with self._manager.execution_credentials(self._session) as (
            server_url,
            auth_token,
        ):
            try:
                events = stream_scratchpad_code(
                    self._session,
                    self._request,
                    code=self._code,
                    http_request=self._http_request,
                    server_url=server_url,
                    auth_token=auth_token,
                )
            except Exception:
                LOGGER.exception("Failed to begin local discovery execution")
                await _error(500, "Failed to execute code")(
                    scope, receive, send
                )
                return

            # A failed ASGI send can leave the iterator suspended at a yield.
            async with aclosing(events):
                await StreamingResponse(
                    events, media_type="text/event-stream"
                )(scope, receive, send)


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


@router.post("/sessions/{session_id}/execute")
async def execute(*, request: Request) -> Response:
    """Execute code in a running session using the scratchpad SSE stream."""
    manager = _manager(request)
    session = manager.session_manager.sessions.get(
        SessionId(request.path_params["session_id"])
    )
    if session is None:
        return _error(404, "Session not found")
    if session.kernel_state() is not KernelState.RUNNING:
        return _error(409, "Session is not running")
    try:
        body = await parse_request(request, cls=ExecuteRequest)
    except (msgspec.ValidationError, ValueError, TypeError) as e:
        return _error(400, str(e))

    # Never pass the discovery credential, cookies, or authenticated user into
    # notebook code. Screenshot callbacks receive a separate one-time token.
    http_request = HTTPRequest.from_request(request)
    http_request.headers = {
        key: value
        for key, value in http_request.headers.items()
        if key.lower() not in {"authorization", "cookie"}
    }
    http_request.query_params = {}
    http_request.cookies = {}
    http_request.user = {}
    return _ExecutionResponse(
        manager=manager,
        session=session,
        request=request,
        code=body.code,
        http_request=http_request,
    )
