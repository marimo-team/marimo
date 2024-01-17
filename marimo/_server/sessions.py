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

import multiprocessing as mp
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
from multiprocessing import connection
from typing import Any, Optional
from uuid import uuid4

from marimo import _loggers
from marimo._ast import codegen
from marimo._ast.app import App, _AppConfig
from marimo._messaging.ops import Alert, serialize
from marimo._output.formatters.formatters import register_formatters
from marimo._runtime import requests, runtime
from marimo._server.model import (
    ConnectionState,
    SessionHandler,
    SessionMode,
)
from marimo._server.utils import import_files, print_tabbed

LOGGER = _loggers.marimo_logger()
SESSION_MANAGER: Optional["SessionManager"] = None


class Session:
    """A client session.

    Each session has its own Python kernel, for editing and running the app,
    and its own websocket, for sending messages to the client.
    """

    TTL_SECONDS = 120

    def __init__(
        self,
        session_handler: SessionHandler,
    ) -> None:
        """Initialize kernel and client connection to it."""
        mpctx = mp.get_context("spawn")
        mgr: SessionManager = get_manager()
        self.session_handler = session_handler

        # Control messages for the kernel (run, autocomplete,
        # set UI element, set config, etc ) are sent through the control queue
        self.control_queue: mp.Queue[requests.Request] | queue.Queue[
            requests.Request
        ]
        # Input messages for the user's Python code are sent through the
        # input queue
        self.input_queue: mp.Queue[str] | queue.Queue[str]

        self.kernel_task: threading.Thread | mp.Process
        self.read_conn: connection.Connection

        app = mgr.load_app()
        configs = (
            {cell_id: data.config for cell_id, data in app._cell_data.items()}
            if app is not None
            else {}
        )
        # Need to use a socket for windows compatibility
        listener = connection.Listener(family="AF_INET")
        is_edit_mode = mgr.mode == SessionMode.EDIT
        if is_edit_mode:
            # We use a process in edit mode so that we can interrupt the app
            # with a SIGINT; we don't mind the additional memory consumption,
            # since there's only one client session
            self.control_queue = mpctx.Queue()
            self.input_queue = mpctx.Queue(maxsize=1)
            self.kernel_task = mp.Process(
                target=runtime.launch_kernel,
                args=(
                    self.control_queue,
                    self.input_queue,
                    listener.address,
                    is_edit_mode,
                    configs,
                ),
                # The process can't be a daemon, because daemonic processes
                # can't create children
                # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Process.daemon  # noqa: E501
                daemon=False,
            )
        else:
            # We use threads in run mode to minimize memory consumption;
            # launching a process would copy the entire program state,
            # which (as of writing) is around 150MB
            self.control_queue = queue.Queue()
            self.input_queue = queue.Queue(maxsize=1)

            # We can't terminate threads, so we have to wait until they
            # naturally exit before cleaning up resources
            def launch_kernel_with_cleanup(*args: Any) -> None:
                runtime.launch_kernel(*args)
                self.read_conn.close()

            # install formatter import hooks, which will be shared by all
            # threads (in edit mode, the single kernel process installs
            # formatters ...)
            register_formatters()

            # Make threads daemons so killing the server immediately brings
            # down all client sessions
            self.kernel_task = threading.Thread(
                target=launch_kernel_with_cleanup,
                args=(
                    self.control_queue,
                    self.input_queue,
                    listener.address,
                    is_edit_mode,
                    configs,
                ),
                # daemon threads can create child processes, unlike
                # daemon processes
                daemon=True,
            )
        self.kernel_task.start()
        # First thing kernel does is connect to the socket, so it's safe to
        # call accept
        self.read_conn = listener.accept()

        def check_alive() -> None:
            if not self.kernel_task.is_alive():
                self.close()
                print()
                print_tabbed(
                    "\033[31mThe Python kernel died unexpectedly.\033[0m"
                )
                print()
                sys.exit()

        session_handler.on_start(
            mode=mgr.mode, connection=self.read_conn, check_alive=check_alive
        )

    def try_interrupt(self) -> None:
        if (
            isinstance(self.kernel_task, mp.Process)
            and self.kernel_task.pid is not None
        ):
            LOGGER.debug("Sending SIGINT to kernel")
            os.kill(self.kernel_task.pid, signal.SIGINT)

    def close(self) -> None:
        """Close kernel, sockets, and pipes."""
        if isinstance(self.kernel_task, mp.Process):
            # type ignores:
            # guaranteed to be a multiprocessing Queue; annoying to assert
            # this, because mp.Queue appears to be a function
            #
            # don't care if the queues still have things in it; don't make the
            # child process wait for it to empty.
            self.control_queue.cancel_join_thread()  # type: ignore
            self.control_queue.close()  # type: ignore
            self.input_queue.cancel_join_thread()  # type: ignore
            self.input_queue.close()  # type: ignore
            if self.kernel_task.is_alive():
                # Explicitly terminate the process
                self.kernel_task.terminate()
            self.read_conn.close()
        elif self.kernel_task.is_alive():
            # kernel thread cleans up read/write conn and IOloop handler on
            # exit; we don't join the thread because we don't want to block
            self.control_queue.put(requests.StopRequest())

        self.session_handler.on_stop(self.read_conn)


class SessionManager:
    """Mapping from client session IDs to sessions.

    Maintains a mapping from client session IDs to client sessions;
    there is exactly one session per client.

    The SessionManager also encapsulates state common to all sessions:
    - the app filename
    - the app mode (edit or run)
    - the server token
    """

    def __init__(
        self,
        filename: Optional[str],
        mode: SessionMode,
        port: int,
        development_mode: bool,
        quiet: bool,
        include_code: bool,
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
        self.include_code = include_code
        # token uniquely identifying this server

        if (app := self.load_app()) is not None:
            self.app_config = app._config
        else:
            self.app_config = None

        if mode == SessionMode.EDIT:
            # In edit mode, the server gets a random token to prevent
            # frontends that it didn't create from connecting to it and
            # executing edit-only commands (such as overwriting the file).
            self.server_token = str(uuid4())
        else:
            # Because run-mode is read-only, all that matters is that
            # the frontend's app matches the server's app.
            assert app is not None
            self.server_token = str(
                hash("".join(code for code in app._codes()))
            )

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
        self, session_id: str, session_handler: SessionHandler
    ) -> Session:
        """Create a new session"""
        LOGGER.debug("creating new session for id %s", session_id)
        if session_id not in self.sessions:
            s = Session(session_handler=session_handler)
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
            if (
                session.session_handler.connection_state()
                == ConnectionState.OPEN
            ):
                return True
        return False

    def start_lsp_server(self) -> None:
        """Starts the lsp server if it is not already started.

        Doesn't start in run mode.
        """
        if self.lsp_process is not None or self.mode == SessionMode.RUN:
            LOGGER.debug("LSP server already started")
            return

        binpath = shutil.which("node")
        if binpath is None:
            LOGGER.error("Node.js not found; cannot start LSP server.")
            for _, session in self.sessions.items():
                session.session_handler.write_operation(
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

        cmd = None
        try:
            LOGGER.debug("Starting LSP server at port %s...", self.lsp_port)
            lsp_bin = os.path.join(
                str(import_files("marimo").joinpath("_lsp")),
                "index.js",
            )
            cmd = f"node {lsp_bin} --port {self.lsp_port}"
            LOGGER.debug("... running command: %s", cmd)
            self.lsp_process = subprocess.Popen(
                cmd.split(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            LOGGER.debug(
                "... node process return code (`None` means success): %s",
                self.lsp_process.returncode,
            )
            LOGGER.debug("Started LSP server at port %s", self.lsp_port)
        except Exception as e:
            LOGGER.error(
                "When starting language server (%s), got error: %s",
                cmd,
                e,
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
        LOGGER.debug("Shutting down")
        self.close_all_sessions()
        if self.lsp_process is not None:
            self.lsp_process.terminate()

    def should_send_code_to_frontend(self) -> bool:
        """Returns True if the server can send messages to the frontend."""
        return self.mode == SessionMode.EDIT or self.include_code


def initialize_manager(
    filename: Optional[str],
    mode: SessionMode,
    port: int,
    development_mode: bool,
    quiet: bool,
    include_code: bool,
) -> SessionManager:
    """Must be called on server start."""
    global SESSION_MANAGER
    SESSION_MANAGER = SessionManager(
        filename=filename,
        mode=mode,
        port=port,
        development_mode=development_mode,
        quiet=quiet,
        include_code=include_code,
    )
    return SESSION_MANAGER


def get_manager() -> SessionManager:
    """Cannot be called until manager has been initialized."""
    assert SESSION_MANAGER is not None
    return SESSION_MANAGER
