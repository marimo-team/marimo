# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import os
from multiprocessing.connection import Connection
from typing import Any, Callable, Optional

import tornado.httputil
import tornado.ioloop
import tornado.web
import tornado.websocket

from marimo import _loggers
from marimo._ast.cell import CellConfig
from marimo._messaging.ops import KernelReady, serialize
from marimo._plugins.core.json_encoder import WebComponentEncoder
from marimo._server.layout import LayoutConfig, read_layout_config
from marimo._server.model import ConnectionState, SessionHandler, SessionMode
from marimo._server.sessions import Session, get_manager

LOGGER = _loggers.marimo_logger()


class IOSocketHandler(tornado.websocket.WebSocketHandler):
    """WebSocket that sessions use to send messages to frontends.

    Each new socket gets a unique session. At most one session can exist when
    in edit mode.
    """

    status: ConnectionState
    cancel_close_handle: Optional[object] = None

    def write_op(self, op: str, data: Any) -> asyncio.Future[None]:
        """Send a message to the client.

        Args:
        ----
        op: name of the operation
        data: JSON-serializable operation data
        """
        try:
            return self.write_message(
                json.dumps(
                    {
                        "op": op,
                        "data": data,
                    },
                    cls=WebComponentEncoder,
                )
            )
        except tornado.websocket.WebSocketClosedError:
            LOGGER.info(
                "Failed to send operation to frontend because the socket "
                f"was closed; op: {op}"
            )

            async def return_none() -> None:
                pass

            return asyncio.ensure_future(return_none())

    def write_kernel_ready(self) -> None:
        """Communicates to the client that the kernel is ready.

        Sends cell code and other metadata to client.
        """
        mgr = get_manager()
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

        self.write_op(
            op=KernelReady.name,
            data=serialize(
                KernelReady(
                    codes=codes, names=names, configs=configs, layout=layout
                )
            ),
        )

    def reconnect_session(self, session: "Session") -> None:
        """Reconnect to an existing session (kernel).

        A websocket can be closed when a user's computer goes to sleep,
        spurious network issues, etc.
        """
        session_handler = session.session_handler
        assert isinstance(session_handler, TornadoWebsocketSessionHandler)
        assert session_handler.websocket.status == ConnectionState.CLOSED
        self.status = ConnectionState.OPEN
        session_handler.websocket = self

    def open(self, *args: str, **kwargs: str) -> None:
        del args
        del kwargs
        try:
            session_id = self.get_query_argument("session_id")
            if session_id is None:
                raise tornado.web.MissingArgumentError("session_id is None")
        except tornado.web.MissingArgumentError:
            LOGGER.error("Malformed connection URL, missing session_id")
            self.close(1003, "MARIMO_MALFORMED_QUERY")
            return
        self.session_id = session_id

        mgr = get_manager()
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
                self.close(1003, "MARIMO_ALREADY_CONNECTED")
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
                    session_handler=TornadoWebsocketSessionHandler(self),
                )
                self.status = ConnectionState.OPEN
                self.write_kernel_ready()
        elif session is not None:
            LOGGER.debug("Reconnecting session %s", session_id)
            # Cancel previous close handle
            self.cancel_close_handle = None
            self.reconnect_session(session)
        else:
            mgr.create_session(
                session_id=session_id,
                session_handler=TornadoWebsocketSessionHandler(self),
            )
            self.status = ConnectionState.OPEN
            # Let the frontend know it can instantiate the app.
            self.write_kernel_ready()

    def on_close(self) -> None:
        """
        When the websocket is closed, we wait TTL_SECONDS before closing the
        session. This is to prevent the session from being closed if the
        during an intermittent network issue.
        """
        LOGGER.debug("websocket connection for %s closed", self.session_id)
        self.status = ConnectionState.CLOSED
        mgr = get_manager()
        if mgr.mode == SessionMode.RUN:

            def _close() -> None:
                if self.status != ConnectionState.OPEN:
                    LOGGER.debug(
                        "Closing session %s (TTL EXPIRED)", self.session_id
                    )
                    mgr.close_session(self.session_id)

            session = mgr.get_session(self.session_id)
            cancellation_handle = tornado.ioloop.IOLoop.current().call_later(
                Session.TTL_SECONDS, _close
            )
            if session is not None:
                self.cancel_close_handle = cancellation_handle


class TornadoWebsocketSessionHandler(SessionHandler):
    """
    Implements a session handler for tornado websockets
    """

    mode: Optional[SessionMode] = None

    def __init__(self, websocket: IOSocketHandler):
        self.websocket = websocket

    def on_start(
        self,
        mode: SessionMode,
        connection: Connection,
        check_alive: Callable[[], None],
    ) -> None:
        self.mode = mode
        if mode == SessionMode.RUN:
            loop = tornado.ioloop.IOLoop.current()
            loop.remove_handler(connection.fileno())

        def reader(fd: int, events: int) -> None:
            del fd
            del events
            (op, data) = connection.recv()
            self.websocket.write_op(op=op, data=data)

        tornado.ioloop.IOLoop.current().add_handler(
            connection.fileno(),
            reader,
            events=(tornado.ioloop.IOLoop.READ),
        )

        # Start a heartbeat to check if the kernel is still alive
        self.kernel_heartbeat = tornado.ioloop.PeriodicCallback(
            check_alive, callback_time=1000.0
        )
        self.kernel_heartbeat.start()

    def write_operation(self, op: str, data: Any) -> None:
        self.websocket.write_op(op=op, data=data)

    def on_stop(self, connection: Connection) -> None:
        # Stop the heartbeat
        if self.kernel_heartbeat.is_running():
            self.kernel_heartbeat.stop()

        if self.mode == SessionMode.RUN:
            tornado.ioloop.IOLoop.current().remove_handler(connection.fileno())

        # 1000 - normal closure
        self.websocket.close(1000, "MARIMO_SHUTDOWN")

    def connection_state(self) -> ConnectionState:
        return self.websocket.status
