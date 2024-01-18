# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import os
from enum import Enum
from multiprocessing.connection import Connection
from typing import Any, Callable, Optional, Tuple

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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


@router.websocket("/ws")
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
    heartbeat_task: Optional[asyncio.Task[None]] = None
    # Messages from the kernel are put in this queue
    # to be sent to the frontend
    message_queue: asyncio.Queue[Tuple[str, Any]]

    async def _write_kernel_ready(self) -> None:
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

    def _reconnect_session(self, session: "Session") -> None:
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
        # Create a new queue for this session
        self.message_queue = asyncio.Queue()

        session_id = self.session_id
        mgr = self.manager
        session = mgr.get_session(session_id)
        LOGGER.debug(
            "Websocket open request for session with id %s", session_id
        )
        LOGGER.debug("Existing sessions: %s", mgr.sessions)

        # Only one frontend can be connected at a time in edit mode.
        if mgr.mode == SessionMode.EDIT and mgr.any_clients_connected():
            LOGGER.debug(
                "Refusing connection; a frontend is already connected."
            )
            await self.websocket.close(
                WebSocketCodes.ALREADY_CONNECTED.value,
                "MARIMO_ALREADY_CONNECTED",
            )
            return

        # Handle reconnection
        if session is not None:
            # The session already exists, but it was disconnected.
            # This can happen in local development when the client
            # goes to sleep and wakes later. Just replace the session's
            # socket, but keep its kernel
            LOGGER.debug("Reconnecting session %s", session_id)
            # Cancel previous close handle
            self.cancel_close_handle = None
            self._reconnect_session(session)
        # Create a new session
        else:
            # If the client refreshed their page, there will be one
            # existing session with a closed socket for a different session
            # id; that's why we call `close_all_sessions`.
            if mgr.mode == SessionMode.EDIT:
                mgr.close_all_sessions()

            mgr.create_session(
                session_id=session_id,
                session_handler=self,
            )
            self.status = ConnectionState.OPEN
            # Let the frontend know it can instantiate the app.
            await self._write_kernel_ready()

        async def listen_for_messages() -> None:
            while True:
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

        async def listen_for_disconnect() -> None:
            try:
                await self.websocket.receive_text()
            except WebSocketDisconnect:
                LOGGER.debug(
                    "Websocket disconnected for session %s",
                    self.session_id,
                )

                # Change the status
                self.status = ConnectionState.CLOSED

                # When the websocket is closed, we wait TTL_SECONDS before
                # closing the session. This is to prevent the session from
                # being closed if the during an intermittent network issue.
                if self.manager.mode == SessionMode.RUN:

                    def _close() -> None:
                        if self.status != ConnectionState.OPEN:
                            LOGGER.debug(
                                "Closing session %s (TTL EXPIRED)",
                                self.session_id,
                            )
                            self.manager.close_session(self.session_id)

                    session = self.manager.get_session(self.session_id)
                    cancellation_handle = asyncio.get_event_loop().call_later(
                        Session.TTL_SECONDS, _close
                    )
                    if session is not None:
                        self.cancel_close_handle = cancellation_handle

                # Close and cancel all tasks
                self.message_queue.task_done()

        await asyncio.gather(
            listen_for_messages(),
            listen_for_disconnect(),
        )

    def on_start(
        self,
        mode: SessionMode,
        connection: Connection,
        check_alive: Callable[[], None],
    ) -> None:
        self.mode = mode

        # Add a reader to the connection
        asyncio.get_event_loop().add_reader(
            connection.fileno(),
            lambda: self.message_queue.put_nowait(connection.recv()),
        )

        # Start a heartbeat task
        async def _heartbeat() -> None:
            while True:
                await asyncio.sleep(1)
                check_alive()

        self.heartbeat_task = asyncio.create_task(_heartbeat())

    def write_operation(self, op: str, data: Any) -> None:
        self.message_queue.put_nowait((op, data))

    def on_stop(self, connection: Connection) -> None:
        # Cancel the heartbeat task
        if self.heartbeat_task:
            self.heartbeat_task.cancel()

        # Remove the reader
        if self.mode == SessionMode.RUN:
            asyncio.get_event_loop().remove_reader(connection.fileno())

        # If the websocket is open, send a close message
        if self.status == ConnectionState.OPEN:
            asyncio.create_task(
                self.websocket.close(
                    WebSocketCodes.NORMAL_CLOSE.value, "MARIMO_SHUTDOWN"
                )
            )

    def connection_state(self) -> ConnectionState:
        return self.status
