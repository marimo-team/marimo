# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import os
from enum import Enum
from multiprocessing.connection import Connection
from typing import Any, Callable, Optional, Tuple

from fastapi import APIRouter, WebSocket

from marimo import _loggers
from marimo._ast.cell import CellConfig
from marimo._messaging.ops import KernelReady, serialize
from marimo._plugins.core.json_encoder import WebComponentEncoder
from marimo._server.layout import LayoutConfig, read_layout_config
from marimo._server.model import ConnectionState, SessionHandler, SessionMode
from marimo._server.sessions import Session, SessionManager
from marimo._server2.api.deps import SessionManagerDep

LOGGER = _loggers.marimo_logger()

router = APIRouter()


class WebSocketCodes(Enum):
    ALREADY_CONNECTED = 1003
    NORMAL_CLOSE = 1000


@router.websocket("/iosocket")
async def websocket_endpoint(
    websocket: WebSocket,
    manager: SessionManagerDep,
    session_id: str,
) -> None:
    await WebsocketHandler(
        websocket=websocket,
        manager=manager,
        session_id=session_id,
    ).start()


class WebsocketHandler(SessionHandler):
    def __init__(
        self, websocket: WebSocket, manager: SessionManager, session_id: str
    ):
        self.websocket = websocket
        self.manager = manager
        self.session_id = session_id

    """WebSocket that sessions use to send messages to frontends.

    Each new socket gets a unique session. At most one session can exist when
    in edit mode.
    """

    status: ConnectionState
    cancel_close_handle: Optional[object] = None
    # Messages from the kernel are put in this queue
    # to be sent to the frontend
    message_queue = asyncio.Queue[Tuple[str, Any]]()

    async def write_kernel_ready(self) -> None:
        """Communicates to the client that the kernel is ready.

        Sends cell code and other metadata to client.
        """
        mgr = self.manager
        codes: tuple[str, ...]
        names: tuple[str, ...]
        configs: tuple[CellConfig, ...]
        app = mgr.load_app()
        layout: Optional[LayoutConfig] = None
        if app is None:
            codes = ("",)
            names = ("__",)
            configs = (CellConfig(),)
        elif mgr.should_send_code_to_frontend():
            codes, names, configs = tuple(
                zip(
                    *tuple(
                        (cell_data.code, cell_data.name, cell_data.config)
                        for cell_data in app._cell_data.values()
                    )
                )
            )
        else:
            codes, names, configs = tuple(
                zip(
                    *tuple(
                        # Don't send code to frontend in run mode
                        ("", "", cell_data.config)
                        for cell_data in app._cell_data.values()
                    )
                )
            )

        if (
            app
            and app._config.layout_file is not None
            and isinstance(mgr.filename, str)
        ):
            app_dir = os.path.dirname(mgr.filename)
            layout = read_layout_config(app_dir, app._config.layout_file)

        await self.message_queue.put(
            (
                KernelReady.name,
                serialize(
                    KernelReady(
                        codes=codes,
                        names=names,
                        configs=configs,
                        layout=layout,
                    )
                ),
            )
        )

    def reconnect_session(self, session: "Session") -> None:
        """Reconnect to an existing session (kernel).

        A websocket can be closed when a user's computer goes to sleep,
        spurious network issues, etc.
        """
        session_handler = session.session_handler
        assert isinstance(session_handler, WebsocketHandler)
        assert session_handler.status == ConnectionState.CLOSED
        self.status = ConnectionState.OPEN
        session_handler = self

    async def start(self) -> None:
        # Accept the websocket connection
        await self.websocket.accept()

        session_id = self.session_id
        mgr = self.manager
        session = mgr.get_session(session_id)
        LOGGER.debug(
            "websocket open request for session with id %s", session_id
        )
        LOGGER.debug("existing sessions: %s", mgr.sessions)
        if mgr.mode == SessionMode.EDIT:
            if mgr.any_clients_connected():
                LOGGER.debug(
                    "refusing connection; a frontend is already connected."
                )
                await self.websocket.close(
                    WebSocketCodes.ALREADY_CONNECTED.value,
                    "MARIMO_ALREADY_CONNECTED",
                )
            elif session is not None:
                # The session already exists, but it was disconnected.
                # This can happen in local development when the client
                # goes to sleep and wakes later. Just replace the session's
                # socket, but keep its kernel
                LOGGER.debug("Reconnecting session %s", session_id)
                self.reconnect_session(session)
            else:
                # No clients are connected, and we haven't seen this session id
                # before. Create a session.
                #
                # If the client refreshed their page, there will be one
                # existing session with a closed socket for a different session
                # id; that's why we call `close_all_sessions`.
                mgr.close_all_sessions()
                mgr.create_session(
                    session_id=session_id,
                    session_handler=self,
                )
                self.status = ConnectionState.OPEN
                await self.write_kernel_ready()
        elif session is not None:
            LOGGER.debug("Reconnecting session %s", session_id)
            # Cancel previous close handle
            self.cancel_close_handle = None
            self.reconnect_session(session)
        else:
            mgr.create_session(
                session_id=session_id,
                session_handler=self,
            )
            self.status = ConnectionState.OPEN
            # Let the frontend know it can instantiate the app.
            await self.write_kernel_ready()

        # Listen for messages from the kernel and send them to the frontend
        while True:
            try:
                (op, data) = await self.message_queue.get()
                await self.websocket.send_text(
                    json.dumps(
                        {
                            "op": op,
                            "data": data,
                        },
                        cls=WebComponentEncoder,
                    )
                )
            except EOFError:
                break

    def on_close(self) -> None:
        """
        When the websocket is closed, we wait TTL_SECONDS before closing the
        session. This is to prevent the session from being closed if the
        during an intermittent network issue.
        """
        LOGGER.debug("websocket connection for %s closed", self.session_id)
        self.status = ConnectionState.CLOSED
        mgr = self.manager
        if mgr.mode == SessionMode.RUN:

            def _close() -> None:
                if self.status != ConnectionState.OPEN:
                    LOGGER.debug(
                        "Closing session %s (TTL EXPIRED)", self.session_id
                    )
                    mgr.close_session(self.session_id)

            session = mgr.get_session(self.session_id)
            cancellation_handle = asyncio.get_event_loop().call_later(
                Session.TTL_SECONDS, _close
            )
            if session is not None:
                self.cancel_close_handle = cancellation_handle

    heartbeat_task: Optional[asyncio.Task[None]] = None

    def on_start(
        self,
        mode: SessionMode,
        connection: Connection,
        check_alive: Callable[[], None],
    ) -> None:
        self.mode = mode

        asyncio.get_event_loop().add_reader(
            connection.fileno(),
            lambda: self.message_queue.put_nowait(connection.recv()),
        )

        async def _heartbeat() -> None:
            while True:
                await asyncio.sleep(1)
                check_alive()

        self.heartbeat_task = asyncio.create_task(_heartbeat())

    def write_operation(self, op: str, data: Any) -> None:
        self.message_queue.put_nowait((op, data))

    def on_stop(self, connection: Connection) -> None:
        if self.heartbeat_task:
            self.heartbeat_task.cancel()

        if self.mode == SessionMode.RUN:
            asyncio.get_event_loop().remove_reader(connection.fileno())

        asyncio.create_task(
            self.websocket.close(
                WebSocketCodes.NORMAL_CLOSE.value, "MARIMO_SHUTDOWN"
            )
        )

    def connection_state(self) -> ConnectionState:
        return self.status
