# Copyright 2026 Marimo. All rights reserved.
"""Editor sessions carried by the host event socket."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from starlette.websockets import WebSocketDisconnect, WebSocketState

from marimo._messaging.notification import KernelStartupErrorNotification
from marimo._messaging.serde import deserialize_kernel_message
from marimo._server.api.endpoints.ws.session_handler import SessionHandler
from marimo._server.api.endpoints.ws.ws_message_loop import (
    should_filter_operation,
)
from marimo._server.api.endpoints.ws.ws_session_connector import ConnectionType
from marimo._server.codes import WebSocketCloseReason, WebSocketCodes
from marimo._server.host.events import (
    MarimoEvent,
    notification_event,
    serialize_event,
)
from marimo._session.managers.ipc import KernelStartupError
from marimo._utils.asyncio_utils import cancel_and_wait

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

    from marimo._core.notebook import Notebook
    from marimo._core.stream import RoutedEvent
    from marimo._messaging.types import KernelMessage
    from marimo._server.api.endpoints.ws.ws_connection_validator import (
        ConnectionParams,
    )
    from marimo._server.host.bridge import SessionBridge
    from marimo._server.rtc.doc import LoroDocManager
    from marimo._server.session_manager import SessionManager


@dataclass(frozen=True)
class _Close:
    code: int
    reason: str


class EditorEventSocket(SessionHandler):
    """Merge host events with the session's private notification delivery."""

    # Shared-log replay omits native notifications to preserve recipients.
    _replay_notebook_on_reconnect = True

    def __init__(
        self,
        websocket: WebSocket,
        *,
        notebook: Notebook,
        bridge: SessionBridge,
        manager: SessionManager,
        params: ConnectionParams,
        doc_manager: LoroDocManager,
        types: set[str] | None,
        cursor: int | None,
    ) -> None:
        super().__init__(
            manager=manager,
            params=params,
            mode=manager.mode,
            doc_manager=doc_manager,
        )
        self.websocket = websocket
        self.notebook = notebook
        self.bridge = bridge
        self.types = types
        self.cursor = cursor
        self._ready_id = 0
        self._events: asyncio.Queue[RoutedEvent | _Close] = asyncio.Queue()
        self._connection_type = (
            ConnectionType.RTC_EXISTING
            if params.rtc_enabled and not params.kiosk
            else ConnectionType.NEW
        )

    def notify(self, notification: KernelMessage) -> None:
        event = notification_event(
            self.notebook.id, deserialize_kernel_message(notification)
        )
        if event.wanted(self.types):
            self._events.put_nowait(event)

    def _on_host_event(self, event: RoutedEvent) -> None:
        # The session delivers marimo notifications with recipient filtering,
        # including edits that must not echo to the client that sent them.
        if not isinstance(event.event, MarimoEvent) and (
            event.id is None or event.id > self._ready_id
        ):
            self._events.put_nowait(event)

    async def start(self) -> None:
        attachment = self.notebook.attach(identity=self.params.session_id)
        unsubscribe = self.bridge.host.subscribe(
            self._on_host_event,
            notebook_id=self.notebook.id,
            types=self.types,
        )
        try:
            initial = self.bridge.host.events(
                self.cursor, notebook_id=self.notebook.id, types=self.types
            )
            self._ready_id = initial[-1].id or 0
            for event in initial:
                # Session notifications must retain their recipient filtering,
                # including on reconnect; only protocol records use replay.
                if not isinstance(event.event, MarimoEvent):
                    self._events.put_nowait(event)
            await self.websocket.accept()
            async with self._connection_lifetime(self.websocket) as startup:
                sending = asyncio.create_task(self._send_events())

                async def connect_and_listen() -> None:
                    try:
                        _, self._connection_type = await startup
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
                        await sending
                        return
                    except WebSocketDisconnect as exc:
                        self._request_close(exc.code, exc.reason or "")
                        await sending
                        return
                    self._check_status_update()
                    await self._wait_for_disconnect()

                listening = asyncio.create_task(connect_and_listen())
                try:
                    done, _ = await asyncio.wait(
                        (sending, listening),
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in done:
                        task.result()
                except WebSocketDisconnect:
                    pass
                finally:
                    await cancel_and_wait(listening)
                    await cancel_and_wait(sending)
        finally:
            unsubscribe()
            self.notebook.detach(attachment.id)

    async def _send_events(self) -> None:
        while True:
            event = await self._events.get()
            if isinstance(event, _Close):
                if (
                    self.websocket.client_state
                    is not WebSocketState.DISCONNECTED
                ):
                    await self.websocket.close(event.code, event.reason)
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
            await self.websocket.send_text(serialize_event(event))

    async def _wait_for_disconnect(self) -> None:
        while True:
            message = await self.websocket.receive()
            if message["type"] == "websocket.disconnect":
                return

    def _request_close(self, code: int, reason: str) -> None:
        self._events.put_nowait(_Close(code, reason))

    def _is_transport_connected(self) -> bool:
        return self.websocket.application_state is WebSocketState.CONNECTED

    def _cancel_message_loop(self) -> None:
        # on_detach queues a close behind pending notifications.
        pass
