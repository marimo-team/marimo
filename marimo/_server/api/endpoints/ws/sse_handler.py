# Copyright 2026 Marimo. All rights reserved.
"""Server-sent events (SSE) transport for marimo sessions.

An experimental alternative to the `/ws` WebSocket for deployments behind
proxies or services that do not support WebSockets (enabled with
`server.transport = "sse"`). Kernel messages only flow server to client, so
an SSE stream can fully replace the WebSocket: control requests already
arrive over HTTP POST endpoints keyed by the `Marimo-Session-Id` header.

Wire protocol:

- Kernel messages are sent as unnamed SSE events whose `data:` payload is
  identical to the WebSocket text frame (`{"op": ..., "data": ...}`).
- A `close` event carrying `{"code": ..., "reason": ...}` mirrors the
  WebSocket close frame; the stream ends right after it. A stream that ends
  without a `close` event is a transient disconnect, and clients should
  reconnect.
- A `: keep-alive` comment is emitted periodically so intermediaries do not
  time out the idle connection.
"""

from __future__ import annotations

import asyncio
import enum
from typing import TYPE_CHECKING, Union, cast

from starlette.websockets import WebSocketDisconnect

from marimo import _loggers
from marimo._messaging.notification import KernelStartupErrorNotification
from marimo._server.api.endpoints.ws.session_handler import SessionHandler
from marimo._server.api.endpoints.ws.ws_formatter import (
    serialize_notification_for_wire,
)
from marimo._server.api.endpoints.ws.ws_message_loop import (
    prepare_wire_message,
)
from marimo._server.codes import WebSocketCloseReason, WebSocketCodes
from marimo._server.sse import (
    HEARTBEAT_EVENT,
    format_close_event,
    format_sse_event,
    wait_for_http_disconnect,
)
from marimo._session.managers.ipc import KernelStartupError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from starlette.requests import Request

    from marimo._messaging.types import KernelMessage
    from marimo._server.api.endpoints.ws.ws_connection_validator import (
        ConnectionParams,
    )
    from marimo._server.rtc.doc import LoroDocManager
    from marimo._server.session_manager import SessionManager
    from marimo._session.model import SessionMode

LOGGER = _loggers.marimo_logger()


class _Signal(enum.Enum):
    """Control markers interleaved with kernel messages in the queue.

    Enqueuing CLOSE behind pending kernel messages means those messages
    are flushed to the client before the close event is sent.
    """

    CLOSE = "close"
    DISCONNECT = "disconnect"
    HEARTBEAT = "heartbeat"


_QueueItem = Union["KernelMessage", _Signal]


class SSESessionHandler(SessionHandler):
    """SSE stream that sessions use to send messages to frontends.

    The SSE analogue of `WebSocketHandler`: connects to a session through
    the shared `SessionConnector`, then streams the message queue as
    server-sent events. The session connection is established lazily on
    the first iteration of `stream()`, so a response that is never
    consumed never attaches a consumer.
    """

    def __init__(
        self,
        *,
        request: Request,
        manager: SessionManager,
        params: ConnectionParams,
        mode: SessionMode,
        doc_manager: LoroDocManager,
        heartbeat_seconds: float = 20.0,
    ):
        super().__init__(
            manager=manager,
            params=params,
            mode=mode,
            doc_manager=doc_manager,
        )
        self.request = request
        self.heartbeat_seconds = heartbeat_seconds
        self._close_code: int | None = None
        self._close_reason: str | None = None
        self._close_requested = False
        self._stream_finished = False
        # One queue carries both kernel messages (via the base class's
        # `notify`) and control signals; the cast reconciles the base
        # class's narrower type with the interleaved signals.
        self._queue: asyncio.Queue[_QueueItem] = asyncio.Queue()
        self.message_queue = cast("asyncio.Queue[KernelMessage]", self._queue)

    async def stream(self) -> AsyncGenerator[str, None]:
        """Connect to the session and stream kernel messages as SSE.

        Connection rejections and kernel startup failures are delivered
        in-band as a `close` event (after a kernel-startup-error message
        when applicable), so the frontend handles every failure through
        the same close-reason path as WebSocket close frames.

        Ends with a `close` event when the server closes the connection
        (shutdown, takeover); ends without one on client disconnect.
        """
        try:
            session, connection_type = self._connect_session(self.request)
        except KernelStartupError as e:
            LOGGER.error("Kernel startup failed: %s", e)
            yield format_sse_event(
                serialize_notification_for_wire(
                    KernelStartupErrorNotification(error=str(e))
                )
            )
            yield format_close_event(
                WebSocketCodes.UNEXPECTED_ERROR,
                WebSocketCloseReason.KERNEL_STARTUP_ERROR,
            )
            return
        except WebSocketDisconnect as e:
            # SessionConnector signals connection rejections (e.g. kiosk
            # not allowed) with WebSocketDisconnect regardless of
            # transport.
            yield format_close_event(e.code, e.reason or "")
            return

        LOGGER.debug(
            "Connected to session %s with type %s",
            session.initialization_id,
            connection_type,
        )

        disconnect_task = asyncio.create_task(self._signal_on_disconnect())
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._check_status_update()
        try:
            while True:
                item = await self._queue.get()
                if item is _Signal.DISCONNECT:
                    return
                if item is _Signal.CLOSE:
                    if self._close_code is not None:
                        yield format_close_event(
                            self._close_code, self._close_reason or ""
                        )
                    return
                if item is _Signal.HEARTBEAT:
                    yield HEARTBEAT_EVENT
                    continue
                text = prepare_wire_message(
                    item,
                    is_kiosk=self._is_viewer(session, connection_type),
                )
                if text is not None:
                    yield format_sse_event(text)
        finally:
            # Also runs when the client disconnects and StreamingResponse
            # cancels the generator; don't await anything cancellable here.
            self._stream_finished = True
            disconnect_task.cancel()
            heartbeat_task.cancel()
            if not self._close_requested:
                self._on_disconnect(
                    ConnectionError("SSE client disconnected"),
                    lambda: None,
                )

    async def _signal_on_disconnect(self) -> None:
        """Signal the stream loop when the client disconnects.

        This is a prompt-shutdown path, not the only cleanup path: when
        the ASGI server (or Starlette itself, on ASGI spec < 2.4) reacts
        to the disconnect first, the generator is cancelled and its
        `finally` performs the same teardown.
        """
        await wait_for_http_disconnect(self.request)
        self._queue.put_nowait(_Signal.DISCONNECT)

    async def _heartbeat_loop(self) -> None:
        """Enqueue a keep-alive comment periodically."""
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            self._queue.put_nowait(_Signal.HEARTBEAT)

    # Transport surface

    def _request_close(self, code: int, reason: str) -> None:
        self._close_code = code
        self._close_reason = reason
        self._close_requested = True
        self._queue.put_nowait(_Signal.CLOSE)

    def _is_transport_connected(self) -> bool:
        return not self._stream_finished

    def _cancel_message_loop(self) -> None:
        self._close_requested = True
        self._queue.put_nowait(_Signal.CLOSE)
