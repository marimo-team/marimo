# Copyright 2023 Marimo. All rights reserved.
"""Client session management

This module encapsulates session management: each client gets a unique session,
and each session wraps a Python kernel and a websocket connection through which
the kernel can send messages to the frontend. Sessions do not share kernels or
websockets.

In run mode, in which we may have many clients connected to the server, a
session is closed as soon as its websocket connection is severed. In edit mode,
in which we have at most one connected client, a session may be kept around
even if its socket is closed.
"""
from __future__ import annotations

import asyncio
import functools
import multiprocessing as mp
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
from enum import Enum
from multiprocessing import connection
from typing import Any, Callable, Optional

import importlib_resources
import tornado.httputil
import tornado.ioloop
import tornado.web
import tornado.websocket

from marimo import _loggers
from marimo._ast import codegen
from marimo._ast.app import App, _AppConfig
from marimo._ast.cell import CellConfig
from marimo._messaging.ops import Alert, KernelReady, serialize
from marimo._output.formatters.formatters import register_formatters
from marimo._runtime import requests, runtime
from marimo._server.api.status import HTTPStatus
from marimo._server.layout import LayoutConfig, read_layout_config
from marimo._server.utils import print_tabbed

LOGGER = _loggers.marimo_logger()
SESSION_MANAGER: Optional["SessionManager"] = None


class ConnectionState(Enum):
    OPEN = 0
    CLOSED = 1


class IOSocketHandler(tornado.websocket.WebSocketHandler):
    """WebSocket that sessions use to send messages to frontends.

    Each new socket gets a unique session. At most one session can exist when
    in edit mode.
    """

    status: ConnectionState

    def write_op(self, op: str, data: Any) -> asyncio.Future[None]:
        """Send a message to the client.

        Args:
        ----
        op: name of the operation
        data: JSON-serializable operation data
        """
        try:
            return self.write_message(
                {
                    "op": op,
                    "data": data,
                }
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
        elif mgr.mode == SessionMode.EDIT:
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
        assert session.socket.status == ConnectionState.CLOSED
        self.status = ConnectionState.OPEN
        session.socket = self

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
                mgr.create_session(session_id=session_id, socket_handler=self)
                self.status = ConnectionState.OPEN
                self.write_kernel_ready()
        elif session is not None:
            LOGGER.debug("Reconnecting session %s", session_id)
            session.cancel_close()
            self.reconnect_session(session)
        else:
            mgr.create_session(session_id=session_id, socket_handler=self)
            self.status = ConnectionState.OPEN
            # Let the frontend know it can instantiate the app.
            self.write_kernel_ready()

    def on_close(self) -> None:
        LOGGER.debug("websocket connection for %s closed", self.session_id)
        self.status = ConnectionState.CLOSED
        mgr = get_manager()
        if mgr.mode == SessionMode.RUN:
            # TODO: keep alive
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
                session.cancel_close_handle = cancellation_handle


class Session:
    """A client session.

    Each session has its own Python kernel, for editing and running the app,
    and its own websocket, for sending messages to the client.
    """

    TTL_SECONDS = 120

    def __init__(self, socket_handler: IOSocketHandler) -> None:
        """Initialize kernel and client connection to it."""
        mpctx = mp.get_context("spawn")
        mgr = get_manager()
        self.socket = socket_handler
        self.cancel_close_handle: Optional[object] = None
        self.queue: mp.Queue[requests.Request] | queue.Queue[requests.Request]
        self.kernel_task: threading.Thread | mp.Process
        self.read_conn: connection.Connection

        # Need to use a socket for windows compatibility
        listener = connection.Listener(family="AF_INET")
        is_edit_mode = mgr.mode == SessionMode.EDIT
        if is_edit_mode:
            # We use a process in edit mode so that we can interrupt the app
            # with a SIGINT; we don't mind the additional memory consumption,
            # since there's only one client session
            self.queue = mpctx.Queue()
            self.kernel_task = mp.Process(
                target=runtime.launch_kernel,
                args=(self.queue, listener.address, is_edit_mode),
                daemon=True,
            )
        else:
            # We use threads in run mode to minimize memory consumption;
            # launching a process would copy the entire program state,
            # which (as of writing) is around 150MB
            self.queue = queue.Queue()
            loop = tornado.ioloop.IOLoop.current()

            # We can't terminate threads, so we have to wait until they
            # naturally exit before cleaning up resources
            def launch_kernel_with_cleanup(*args: Any) -> None:
                runtime.launch_kernel(*args)
                loop.remove_handler(self.read_conn.fileno())
                self.read_conn.close()

            # install formatter import hooks, which will be shared by all
            # threads (in edit mode, the single kernel process installs
            # formatters ...)
            register_formatters()

            # Make threads daemons so killing the server immediately brings
            # down all client sessions
            self.kernel_task = threading.Thread(
                target=launch_kernel_with_cleanup,
                args=(self.queue, listener.address, is_edit_mode),
                daemon=True,
            )
        self.kernel_task.start()
        # First thing kernel does is connect to the socket, so it's safe to
        # call accept
        self.read_conn = listener.accept()

        def reader(fd: int, events: int) -> None:
            del fd
            del events
            (op, data) = self.read_conn.recv()
            self.socket.write_op(op=op, data=data)

        tornado.ioloop.IOLoop.current().add_handler(
            self.read_conn.fileno(),
            reader,
            events=(tornado.ioloop.IOLoop.READ),
        )

        def check_alive() -> None:
            if not self.kernel_task.is_alive():
                self.close()
                print()
                print_tabbed(
                    "\033[31mThe Python kernel died unexpectedly.\033[0m"
                )
                print()
                sys.exit()

        self.kernel_heartbeat = tornado.ioloop.PeriodicCallback(
            check_alive, callback_time=1000.0
        )
        self.kernel_heartbeat.start()

    def try_interrupt(self) -> None:
        if (
            isinstance(self.kernel_task, mp.Process)
            and self.kernel_task.pid is not None
        ):
            LOGGER.debug("Sending SIGINT to kernel")
            os.kill(self.kernel_task.pid, signal.SIGINT)

    def close(self) -> None:
        """Close kernel, sockets, and pipes."""
        if self.kernel_heartbeat.is_running():
            self.kernel_heartbeat.stop()
        if isinstance(self.kernel_task, mp.Process):
            # guaranteed to be a multiprocessing Queue; annoying to assert
            # this, because mp.Queue appears to be a function
            self.queue.close()  # type: ignore
            if self.kernel_task.is_alive():
                if (
                    sys.platform == "win32" or sys.platform == "cygwin"
                ) and self.kernel_task.pid is not None:
                    # send a CTRL_BREAK_EVENT to gracefully shutdown
                    # since SIGTERM isn't handled on windows
                    os.kill(self.kernel_task.pid, signal.CTRL_BREAK_EVENT)
                else:
                    self.kernel_task.terminate()
            tornado.ioloop.IOLoop.current().remove_handler(
                self.read_conn.fileno()
            )
            self.read_conn.close()
        elif self.kernel_task.is_alive():
            # kernel thread cleans up read/write conn and IOloop handler on
            # exit; we don't join the thread because we don't want to block
            self.queue.put(requests.StopRequest())
        # 1000 - normal closure
        self.socket.close(1000, "MARIMO_SHUTDOWN")

    def cancel_close(self) -> None:
        if self.cancel_close_handle is not None:
            tornado.ioloop.IOLoop.current().remove_timeout(
                self.cancel_close_handle
            )


class SessionMode(Enum):
    # read-write
    EDIT = 0
    # read-only
    RUN = 1


class SessionManager:
    """Mapping from client session IDs to sessions.

    Maintains a mapping from client session IDs to client sessions;
    there is exactly one session per client.

    The SessionManager also encapsulates state common to all sessions:
    - the app filename
    - the app mode (edit or run)
    """

    def __init__(
        self,
        filename: Optional[str],
        mode: SessionMode,
        port: int,
        development_mode: bool,
        quiet: bool,
    ) -> None:
        self.filename = filename
        self.mode = mode
        self.port = port
        self.lsp_port = int(self.port * 10)
        self.lsp_process: Optional[subprocess.Popen[bytes]] = None
        self.development_mode = development_mode
        self.quiet = quiet
        self.sessions: dict[str, Session] = {}
        self.app_config: Optional[_AppConfig]

        if (app := self.load_app()) is not None:
            self.app_config = app._config
        else:
            self.app_config = None

    def load_app(self) -> Optional[App]:
        return codegen.get_app(self.filename)

    def update_app_config(self, config: dict[str, Any]) -> None:
        if self.app_config is not None:
            self.app_config.update(config)
        else:
            self.app_config = _AppConfig(**config)

    def rename(self, filename: Optional[str]) -> None:
        """Register a change in filename.

        Should be called if an api call renamed the current file on disk.
        """
        self.filename = filename

    def create_session(
        self, session_id: str, socket_handler: IOSocketHandler
    ) -> Session:
        """Create a new session

        The `socket_handler` should already be open.
        """
        LOGGER.debug("creating new session for id %s", session_id)
        if session_id not in self.sessions:
            s = Session(socket_handler=socket_handler)
            self.sessions[session_id] = s
            return s
        else:
            return self.sessions[session_id]

    def get_session(self, session_id: str) -> Optional[Session]:
        if session_id in self.sessions:
            return self.sessions[session_id]
        return None

    def any_clients_connected(self) -> bool:
        """Returns True if at least one client has an open socket."""
        for session in self.sessions.values():
            if session.socket.status == ConnectionState.OPEN:
                return True
        return False

    def start_lsp_server(self) -> None:
        """Starts the lsp server if it is not already started.

        Doesn't start in run mode.
        """
        if self.lsp_process is not None or self.mode == SessionMode.RUN:
            return

        binpath = shutil.which("node")
        if binpath is None:
            for _, session in self.sessions.items():
                session.socket.write_op(
                    Alert.name,
                    serialize(
                        Alert(
                            title="Github Copilot: Connection Error",
                            description="<span><a class='hyperlink' href='https://docs.marimo.io/getting_started/index.html#github-copilot'>Install Node.js</a> to use copilot.</span>",  # noqa: E501
                            variant="danger",
                        )
                    ),
                )
            return

        lsp_bin = os.path.join(
            str(importlib_resources.files("marimo").joinpath("_lsp")),
            "index.js",
        )
        cmd = f"node {lsp_bin} --port {self.lsp_port}"
        try:
            self.lsp_process = subprocess.Popen(
                cmd.split(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            LOGGER.debug("Starting LSP server at port %s", self.lsp_port)
        except Exception as e:
            LOGGER.error(
                "When starting language server (%s), got error: %s", cmd, e
            )

    def close_session(self, session_id: str) -> None:
        LOGGER.debug("closing session %s", session_id)
        session = self.get_session(session_id)
        if session is not None:
            session.close()
            del self.sessions[session_id]

    def close_all_sessions(self) -> None:
        LOGGER.debug("Closing all sessions (sessions: %s)", self.sessions)
        for session in self.sessions.values():
            session.close()
        LOGGER.debug("All sessions closed.")
        self.sessions = {}

    def shutdown(self) -> None:
        self.close_all_sessions()
        if self.lsp_process is not None:
            self.lsp_process.terminate()


def requires_edit(handler: Callable[..., Any]) -> Callable[..., Any]:
    """Mark a function as requiring edit permissions.

    Raises:
    ------
    tornado.web.HTTPError: if session manager is not in edit mode.
    """

    @functools.wraps(handler)
    def _throw_if_not_edit(*args: Any, **kwargs: Any) -> Any:
        if get_manager().mode != SessionMode.EDIT:
            raise tornado.web.HTTPError(HTTPStatus.FORBIDDEN)
        else:
            return handler(*args, **kwargs)

    return _throw_if_not_edit


def initialize_manager(
    filename: Optional[str],
    mode: SessionMode,
    port: int,
    development_mode: bool,
    quiet: bool,
) -> SessionManager:
    """Must be called on server start."""
    global SESSION_MANAGER
    SESSION_MANAGER = SessionManager(
        filename=filename,
        mode=mode,
        port=port,
        development_mode=development_mode,
        quiet=quiet,
    )
    return SESSION_MANAGER


def get_manager() -> SessionManager:
    """Cannot be called until manager has been initialized."""
    assert SESSION_MANAGER is not None
    return SESSION_MANAGER


def session_id_from_header(
    headers: tornado.httputil.HTTPHeaders,
) -> str:
    """Extracts session ID from request header.

    All endpoints require a session ID to be in the request header.
    """
    session_id = headers.get_list("Marimo-Session-Id")
    if not session_id:
        raise RuntimeError(
            "Invalid headers (Marimo-Session-Id not found\n\n)" + str(headers)
        )
    elif len(session_id) > 1:
        raise RuntimeError(
            "Invalid headers (> 1 Marimo-Session-Id\n\n)" + str(headers)
        )
    return session_id[0]


def session_from_header(
    headers: tornado.httputil.HTTPHeaders,
) -> Optional[Session]:
    """Get the Session implied by the request header, if any."""
    session_id = session_id_from_header(headers)
    mgr = get_manager()
    session = mgr.get_session(session_id)
    if session is None:
        LOGGER.error("Session with id %s not found", session_id)
    return session


def require_session_from_header(
    headers: tornado.httputil.HTTPHeaders,
) -> Session:
    """Throws an HTTPError if no Session is found."""
    session = session_from_header(headers)
    if session is None:
        raise tornado.web.HTTPError(HTTPStatus.NOT_FOUND, "Session not found.")
    return session
