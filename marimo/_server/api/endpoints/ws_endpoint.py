# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import aclosing
from typing import TYPE_CHECKING

from starlette.responses import StreamingResponse

from marimo import _loggers
from marimo._server.api.auth import validate_auth
from marimo._server.api.deps import AppState
from marimo._server.api.endpoints.ws.ws_connection_validator import (
    ConnectionRejection,
    WebSocketConnectionValidator,
    parse_connection_params,
)
from marimo._server.codes import WebSocketCloseReason, WebSocketCodes
from marimo._server.host import stream_options
from marimo._server.host.lifespan import ensure_host
from marimo._server.host.session import SessionEventStream
from marimo._server.router import APIRouter
from marimo._server.sse import SSE_HEADERS, format_close_event

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from starlette.requests import Request
    from starlette.websockets import WebSocket

    from marimo._server.api.endpoints.ws.ws_connection_validator import (
        ConnectionParams,
    )

LOGGER = _loggers.marimo_logger()

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
) -> None:
    """Main WebSocket endpoint for marimo sessions.

    responses:
        200:
            description: Websocket endpoint
    """
    app_state = AppState(websocket)
    validator = WebSocketConnectionValidator(websocket, app_state)

    # Validate authentication before proceeding
    if not await validator.validate_auth():
        return

    # Extract and validate connection parameters
    params = await validator.extract_connection_params()
    if params is None:
        return

    try:
        handler = await _session_events(websocket, params)
    except ValueError as exc:
        await websocket.close(code=1008, reason=str(exc))
        return
    await handler.start()


async def _session_events(
    connection: WebSocket | Request, params: ConnectionParams
) -> SessionEventStream:
    cursor = stream_options.cursor(connection)
    types = stream_options.types(connection)
    if "run_id" in connection.query_params:
        raise ValueError("Session streams do not support run_id filtering")
    context = await ensure_host(connection.app)
    return SessionEventStream(
        connection,
        notebook=None,
        bridge=context.bridge,
        manager=AppState(connection).session_manager,
        params=params,
        types=types,
        cursor=cursor,
    )


def _sse_response(events: AsyncGenerator[str, None]) -> StreamingResponse:
    return StreamingResponse(
        events, media_type="text/event-stream", headers=SSE_HEADERS
    )


def _close_only_stream(code: int, reason: str) -> StreamingResponse:
    """A stream carrying just a `close` event.

    Connection errors are delivered in-band (over an HTTP 200 stream) so
    the frontend handles them through the same close-reason path as
    WebSocket close frames.
    """

    async def gen() -> AsyncGenerator[str, None]:
        yield format_close_event(code, reason)

    return _sse_response(gen())


@router.get("/sse", include_in_schema=False)
async def sse_endpoint(request: Request) -> StreamingResponse:
    """Experimental SSE alternative to the main `/ws` endpoint.

    Enabled with `server.transport = "sse"`. Streams host events as
    server-sent events; control requests flow through the regular HTTP
    POST endpoints.

    responses:
        200:
            description: Host events as a server-sent event stream
            content:
                text/event-stream:
                    schema:
                        type: string
    """
    app_state = AppState(request)

    # Validate authentication before proceeding
    if app_state.enable_auth and not validate_auth(request):
        return _close_only_stream(
            WebSocketCodes.UNAUTHORIZED, WebSocketCloseReason.UNAUTHORIZED
        )

    # Extract and validate connection parameters
    params = parse_connection_params(app_state)
    if isinstance(params, ConnectionRejection):
        return _close_only_stream(params.code, params.reason)

    LOGGER.debug(
        "SSE open request for session with id %s",
        params.session_id,
    )

    # The handler connects to the session lazily, on the first iteration
    # of the stream. Connecting here instead would attach a consumer that
    # is never detached if the response body is never consumed.
    async def stream() -> AsyncGenerator[str, None]:
        try:
            handler = await _session_events(request, params)
        except ValueError as exc:
            yield format_close_event(1008, str(exc))
            return
        async with aclosing(handler.sse()) as events:
            async for event in events:
                yield event

    return _sse_response(stream())
