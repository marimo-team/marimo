# Copyright 2026 Marimo. All rights reserved.
"""Editor and app sessions carried by the host event stream."""

from __future__ import annotations

import asyncio
from contextlib import aclosing
from dataclasses import dataclass
from typing import TYPE_CHECKING

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from marimo._core import protocol
from marimo._core.stream import RoutedEvent
from marimo._messaging.notification import KernelStartupErrorNotification
from marimo._messaging.serde import deserialize_kernel_message
from marimo._server.api.endpoints.ws.notification_filter import (
    should_filter_operation,
)
from marimo._server.api.endpoints.ws.session_handler import SessionHandler
from marimo._server.api.endpoints.ws.ws_session_connector import ConnectionType
from marimo._server.codes import WebSocketCloseReason, WebSocketCodes
from marimo._server.host.events import (
    MarimoEvent,
    notification_event,
    serialize_event,
    serialize_sse_event,
)
from marimo._server.sse import (
    HEARTBEAT_EVENT,
    format_close_event,
    wait_for_http_disconnect,
)
from marimo._session.managers.ipc import KernelStartupError
from marimo._utils.asyncio_utils import cancel_and_wait

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from starlette.requests import Request

    from marimo._core.notebook import Notebook
    from marimo._messaging.types import KernelMessage
    from marimo._server.api.endpoints.ws.ws_connection_validator import (
        ConnectionParams,
    )
    from marimo._server.host.bridge import SessionBridge
    from marimo._server.rtc.doc import LoroDocManager
    from marimo._server.session_manager import SessionManager
    from marimo._session.session import Session


@dataclass(frozen=True)
class _Close:
    code: int
    reason: str


class SessionEventStream(SessionHandler):
    """Merge host events with the session's private notification delivery."""

    def __init__(
        self,
        connection: WebSocket | Request,
        *,
        notebook: Notebook | None,
        bridge: SessionBridge,
        manager: SessionManager,
        params: ConnectionParams,
        doc_manager: LoroDocManager,
        types: set[str] | None,
        cursor: str | None,
        heartbeat_seconds: float = 20.0,
    ) -> None:
        super().__init__(
            manager=manager,
            params=params,
            mode=manager.mode,
            doc_manager=doc_manager,
        )
        self.connection = connection
        self.heartbeat_seconds = heartbeat_seconds
        self._stream_finished = False
        self.notebook = notebook
        self.bridge = bridge
        self.types = types
        self.cursor = cursor
        self._attachment: protocol.Attachment | None = None
        self._unsubscribe: Callable[[], None] | None = None
        self._ready_id = 0
        self._events: asyncio.Queue[RoutedEvent | _Close | None] = (
            asyncio.Queue()
        )
        self._connection_type = (
            ConnectionType.RTC_EXISTING
            if params.rtc_enabled and not params.kiosk
            else ConnectionType.NEW
        )

    def notify(self, notification: KernelMessage) -> None:
        event = notification_event(
            self.notebook.id if self.notebook is not None else None,
            deserialize_kernel_message(notification),
        )
        if event.wanted(self.types):
            self._events.put_nowait(event)

    def _on_host_event(self, event: RoutedEvent) -> None:
        # The session delivers marimo notifications with recipient filtering,
        # including edits that must not echo to the client that sent them.
        if not isinstance(event.event, MarimoEvent) and (
            event.position is None or event.position > self._ready_id
        ):
            self._events.put_nowait(event)

    async def _prepare_session(self, session: Session) -> None:
        if self.notebook is None:
            if (
                self.cursor is not None
                and self.bridge.notebook_for_session(session) is None
            ):
                self._events.put_nowait(
                    RoutedEvent(protocol.ResetEvent(data={}))
                )
                self.cursor = None
            notebook = await self.bridge.adopt(session)
            if notebook is None:
                raise WebSocketDisconnect(
                    WebSocketCodes.UNEXPECTED_ERROR, "Notebook unavailable"
                )
            self._subscribe(notebook)
        else:
            await self.bridge.bind(self.notebook.id, session)

    def _subscribe(self, notebook: Notebook) -> None:
        self.notebook = notebook
        self._attachment = notebook.attach(identity=self.params.session_id)
        self._unsubscribe = self.bridge.host.subscribe(
            self._on_host_event, notebook_id=notebook.id, types=self.types
        )
        initial = self.bridge.host.events(
            self.cursor, notebook_id=notebook.id, types=self.types
        )
        self._ready_id = initial[-1].position or 0
        for event in initial:
            # Native replay must retain the session's recipient filtering.
            if not isinstance(event.event, MarimoEvent):
                self._events.put_nowait(event)

    async def stream(
        self,
    ) -> AsyncGenerator[RoutedEvent | _Close | None, None]:
        """Broker the session and deliver its host events until disconnect."""
        try:
            if self.notebook is not None:
                self._subscribe(self.notebook)
            async with self._connection_lifetime(self.connection) as startup:

                async def connect_and_listen() -> None:
                    try:
                        _, self._connection_type = await startup
                        self._check_status_update()
                        await self._wait_for_disconnect()
                    except asyncio.CancelledError:
                        return
                    except KernelStartupError as exc:
                        self._serialize_and_notify(
                            KernelStartupErrorNotification(error=str(exc))
                        )
                        self._request_close(
                            WebSocketCodes.UNEXPECTED_ERROR,
                            WebSocketCloseReason.KERNEL_STARTUP_ERROR,
                        )
                    except WebSocketDisconnect as exc:
                        self._request_close(exc.code, exc.reason or "")
                    finally:
                        self._events.put_nowait(None)

                listening = asyncio.create_task(connect_and_listen())
                try:
                    while True:
                        try:
                            event = await asyncio.wait_for(
                                self._events.get(), self.heartbeat_seconds
                            )
                        except TimeoutError:
                            yield None
                            continue
                        if event is None:
                            await listening
                            return
                        if isinstance(event, _Close):
                            yield event
                            return
                        if isinstance(event.event, MarimoEvent):
                            viewer = self.params.kiosk
                            if self._session is not None:
                                viewer = self._is_viewer(
                                    self._session, self._connection_type
                                )
                            if should_filter_operation(
                                event.event.data.marimo.name, is_kiosk=viewer
                            ):
                                continue
                        yield event
                finally:
                    await cancel_and_wait(listening)
        finally:
            self._stream_finished = True
            if self._unsubscribe is not None:
                self._unsubscribe()
            if self.notebook is not None and self._attachment is not None:
                self.notebook.detach(self._attachment.id)

    def _serialize(self, event: RoutedEvent) -> str:
        return serialize_event(
            event, include_code=self.manager.should_send_code_to_frontend()
        )

    async def start(self) -> None:
        """Deliver the host stream over a WebSocket."""
        websocket = self.connection
        assert isinstance(websocket, WebSocket)
        await websocket.accept()
        try:
            async with aclosing(self.stream()) as events:
                async for event in events:
                    if isinstance(event, _Close):
                        if (
                            websocket.client_state
                            is not WebSocketState.DISCONNECTED
                        ):
                            await websocket.close(event.code, event.reason)
                    elif event is not None:
                        await websocket.send_text(self._serialize(event))
        except WebSocketDisconnect:
            pass

    async def sse(self) -> AsyncGenerator[str, None]:
        """Frame the same host envelopes as SSE, including close and heartbeat."""
        async with aclosing(self.stream()) as events:
            async for event in events:
                if isinstance(event, _Close):
                    yield format_close_event(event.code, event.reason)
                elif event is None:
                    yield HEARTBEAT_EVENT
                else:
                    yield serialize_sse_event(
                        event,
                        include_code=self.manager.should_send_code_to_frontend(),
                    )

    async def _wait_for_disconnect(self) -> None:
        if isinstance(self.connection, WebSocket):
            while True:
                message = await self.connection.receive()
                if message["type"] == "websocket.disconnect":
                    return
        else:
            await wait_for_http_disconnect(self.connection)

    def _request_close(self, code: int, reason: str) -> None:
        self._events.put_nowait(_Close(code, reason))

    def _is_transport_connected(self) -> bool:
        return not self._stream_finished
