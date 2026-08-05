# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

from starlette.responses import StreamingResponse
from starlette.websockets import WebSocket, WebSocketState

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.notification import (
    KernelStartupErrorNotification,
)
from marimo._server.api.auth import validate_auth
from marimo._server.api.deps import AppState
from marimo._server.api.endpoints.ws.session_handler import SessionHandler
from marimo._server.api.endpoints.ws.sse_handler import SSESessionHandler
from marimo._server.api.endpoints.ws.ws_connection_validator import (
    ConnectionRejection,
    WebSocketConnectionValidator,
    parse_connection_params,
)
from marimo._server.api.endpoints.ws.ws_formatter import (
    serialize_notification_for_wire,
)
from marimo._server.api.endpoints.ws.ws_message_loop import (
    WebSocketMessageLoop,
)
from marimo._server.api.endpoints.ws.ws_rtc_handler import RTCWebSocketHandler
from marimo._server.codes import WebSocketCloseReason, WebSocketCodes
from marimo._server.router import APIRouter
from marimo._server.rtc.doc import LoroDocManager
from marimo._server.sse import SSE_HEADERS, format_close_event
from marimo._session.managers.ipc import KernelStartupError
from marimo._session.model import SessionMode

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from starlette.requests import Request

    from marimo._server.api.endpoints.ws.ws_connection_validator import (
        ConnectionParams,
    )
    from marimo._server.session_manager import SessionManager

LOGGER = _loggers.marimo_logger()

LORO_ALLOWED = sys.version_info >= (3, 11)

router = APIRouter()

DOC_MANAGER = LoroDocManager()

# Strong refs so fire-and-forget tasks aren't GC'd mid-flight.
_background_tasks: set[asyncio.Task[None]] = set()


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

    # Start handler
    await WebSocketHandler(
        websocket=websocket,
        manager=app_state.session_manager,
        params=params,
        mode=app_state.mode,
    ).start()


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

    Enabled with `server.transport = "sse"`. Streams kernel messages as
    server-sent events; control requests flow through the regular HTTP
    POST endpoints.

    responses:
        200:
            description: Kernel messages as a server-sent event stream
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

    # Extract and validate connection parameters. SSE cannot carry the
    # /ws_sync document stream, so RTC is disabled.
    params = parse_connection_params(app_state, allow_rtc=False)
    if isinstance(params, ConnectionRejection):
        return _close_only_stream(params.code, params.reason)

    LOGGER.debug(
        "SSE open request for session with id %s",
        params.session_id,
    )

    # The handler connects to the session lazily, on the first iteration
    # of the stream. Connecting here instead would attach a consumer that
    # is never detached if the response body is never consumed.
    handler = SSESessionHandler(
        request=request,
        manager=app_state.session_manager,
        params=params,
        mode=app_state.mode,
        doc_manager=DOC_MANAGER,
    )
    return _sse_response(handler.stream())


# WebSocket endpoint for LoroDoc synchronization
@router.websocket("/ws_sync")
async def ws_sync(
    websocket: WebSocket,
) -> None:
    """WebSocket endpoint for LoroDoc synchronization (RTC)."""
    app_state = AppState(websocket)
    validator = WebSocketConnectionValidator(websocket, app_state)

    # Validate authentication before proceeding
    if not await validator.validate_auth():
        return

    # Check if Loro is available
    if not (LORO_ALLOWED and DependencyManager.loro.has()):
        if not LORO_ALLOWED:
            LOGGER.warning(
                "RTC: Python version is not supported (requires 3.11+)"
            )
        else:
            LOGGER.warning("RTC: Loro is not installed, closing websocket")
        await websocket.close(
            WebSocketCodes.NORMAL_CLOSE,
            WebSocketCloseReason.LORO_NOT_INSTALLED,
        )
        return

    # Extract file key
    file_key = await validator.extract_file_key_only()
    if file_key is None:
        return

    # Verify session exists
    manager = app_state.session_manager
    session = manager.get_session_by_file_key(file_key)
    if session is None:
        LOGGER.warning(
            f"RTC: Closing websocket - no session found for file key {file_key}"
        )
        await websocket.close(
            WebSocketCodes.FORBIDDEN, WebSocketCloseReason.NOT_ALLOWED
        )
        return

    # Handle RTC connection
    handler = RTCWebSocketHandler(websocket, file_key, DOC_MANAGER)
    await handler.handle()


class WebSocketHandler(SessionHandler):
    """WebSocket that sessions use to send messages to frontends.

    Each new socket gets a unique session. At most one session can exist when
    in edit mode (unless RTC is enabled).
    """

    def __init__(
        self,
        *,
        websocket: WebSocket,
        manager: SessionManager,
        params: ConnectionParams,
        mode: SessionMode,
    ):
        super().__init__(
            manager=manager,
            params=params,
            mode=mode,
            doc_manager=DOC_MANAGER,
        )
        self.websocket = websocket
        self.ws_future: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the WebSocket handler.

        Accepts the connection, establishes a session, and starts the
        message loop.
        """
        # Accept the websocket connection
        await self.websocket.accept()

        LOGGER.debug(
            "Websocket open request for session with id %s",
            self.params.session_id,
        )
        LOGGER.debug("Existing sessions: %s", self.manager.sessions)

        try:
            session, connection_type = self._connect_session(self.websocket)
        except KernelStartupError as e:
            LOGGER.error("Kernel startup failed: %s", e)
            await self._close_kernel_startup_error(str(e))
            return
        LOGGER.debug(
            "Connected to session %s with type %s",
            session.initialization_id,
            connection_type,
        )

        # Start message loops
        message_loop = WebSocketMessageLoop(
            websocket=self.websocket,
            message_queue=self.message_queue,
            is_kiosk=lambda: self._is_viewer(session, connection_type),
            on_disconnect=self._on_disconnect,
            on_check_status_update=self._check_status_update,
        )

        try:
            self.ws_future = asyncio.create_task(message_loop.start())
            await self.ws_future
        except asyncio.CancelledError:
            LOGGER.debug("Websocket terminated with CancelledError")

    async def _safe_close(self, code: int, reason: str) -> None:
        """Close the WebSocket, ignoring errors from uninitialized state.

        uvicorn never calls websockets' `connection_open()`, so internal
        attributes like `transfer_data_task` are missing. Closing a
        websocket in that state raises `AttributeError`. The connection
        is cleaned up when the handler returns regardless.
        """
        try:
            await self.websocket.close(code, reason)
        except AttributeError as e:
            if "transfer_data_task" not in str(e):
                raise
            LOGGER.debug(
                "Ignoring AttributeError during websocket close: "
                "missing transfer_data_task",
                exc_info=True,
            )

    async def _close_kernel_startup_error(self, error_message: str) -> None:
        """Send full error as message, then close the WebSocket."""
        if self.websocket.application_state is WebSocketState.CONNECTED:
            notification = KernelStartupErrorNotification(error=error_message)
            text = serialize_notification_for_wire(notification)
            await self.websocket.send_text(text)
            # Then close with simple reason
            await self._safe_close(
                WebSocketCodes.UNEXPECTED_ERROR,
                WebSocketCloseReason.KERNEL_STARTUP_ERROR,
            )

    def _request_close(self, code: int, reason: str) -> None:
        task = asyncio.create_task(self._safe_close(code, reason))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    def _is_transport_connected(self) -> bool:
        return self.websocket.application_state is WebSocketState.CONNECTED

    def _cancel_message_loop(self) -> None:
        if self.ws_future:
            self.ws_future.cancel()
