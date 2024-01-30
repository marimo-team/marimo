# Copyright 2024 Marimo. All rights reserved.
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
from multiprocessing.queues import Queue as MPQueue
from typing import Any, Optional
from uuid import uuid4

from marimo import _loggers
from marimo._ast import codegen
from marimo._ast.app import App, InternalApp, _AppConfig
from marimo._ast.cell import CellConfig, CellId_t
from marimo._messaging.ops import Alert, serialize
from marimo._output.formatters.formatters import register_formatters
from marimo._runtime import requests, runtime
from marimo._runtime.requests import AppMetadata
from marimo._server.model import (
    ConnectionState,
    SessionHandler,
    SessionMode,
)
from marimo._server.types import QueueType
from marimo._server.utils import import_files, print_tabbed

LOGGER = _loggers.marimo_logger()
SESSION_MANAGER: Optional["SessionManager"] = None


class QueueManager:
    """Manages queues for a session."""

    def __init__(self, use_multiprocessing: bool):
        context = mp.get_context("spawn") if use_multiprocessing else None
        # Control messages for the kernel (run, autocomplete,
        # set UI element, set config, etc ) are sent through the control queue
        self.control_queue: QueueType[requests.Request] = (
            context.Queue() if context is not None else queue.Queue()
        )
        # Input messages for the user's Python code are sent through the
        # input queue
        self.input_queue: QueueType[str] = (
            context.Queue(maxsize=1)
            if context is not None
            else queue.Queue(maxsize=1)
        )

    def close_queues(self) -> None:
        if isinstance(self.control_queue, MPQueue):
            # cancel join thread because we don't care if the queues still have
            # things in it: don't want to make the child process wait for the
            # queues to empty
            self.control_queue.cancel_join_thread()
            self.control_queue.close()
        else:
            # kernel thread cleans up read/write conn and IOloop handler on
            # exit; we don't join the thread because we don't want to block
            self.control_queue.put(requests.StopRequest())

        if isinstance(self.input_queue, MPQueue):
            # again, don't make the child process wait for the queues to empty
            self.input_queue.cancel_join_thread()
            self.input_queue.close()


class KernelManager:
    def __init__(
        self,
        queue_manager: QueueManager,
        mode: SessionMode,
        configs: dict[CellId_t, CellConfig],
        app_metadata: AppMetadata,
    ) -> None:
        self.kernel_task: Optional[threading.Thread] | Optional[mp.Process]
        self.queue_manager = queue_manager
        self.mode = mode
        self.configs = configs
        self._read_conn: Optional[connection.Connection] = None
        self.app_metadata = app_metadata

    def start_kernel(self) -> None:
        # Need to use a socket for windows compatibility
        listener = connection.Listener(family="AF_INET")

        # We use a process in edit mode so that we can interrupt the app
        # with a SIGINT; we don't mind the additional memory consumption,
        # since there's only one client sess
        is_edit_mode = self.mode == SessionMode.EDIT
        if is_edit_mode:
            self.kernel_task = mp.Process(
                target=runtime.launch_kernel,
                args=(
                    self.queue_manager.control_queue,
                    self.queue_manager.input_queue,
                    listener.address,
                    is_edit_mode,
                    self.configs,
                    self.app_metadata,
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

            # We can't terminate threads, so we have to wait until they
            # naturally exit before cleaning up resources
            def launch_kernel_with_cleanup(*args: Any) -> None:
                runtime.launch_kernel(*args)
                self.kernel_connection.close()

            # install formatter import hooks, which will be shared by all
            # threads (in edit mode, the single kernel process installs
            # formatters ...)
            register_formatters()

            # Make threads daemons so killing the server immediately brings
            # down all client sessions
            self.kernel_task = threading.Thread(
                target=launch_kernel_with_cleanup,
                args=(
                    self.queue_manager.control_queue,
                    self.queue_manager.input_queue,
                    listener.address,
                    is_edit_mode,
                    self.configs,
                    self.app_metadata,
                ),
                # daemon threads can create child processes, unlike
                # daemon processes
                daemon=True,
            )

        self.kernel_task.start()  # type: ignore
        # First thing kernel does is connect to the socket, so it's safe to
        # call accept
        self._read_conn = listener.accept()

    def is_alive(self) -> bool:
        return self.kernel_task is not None and self.kernel_task.is_alive()

    def interrupt_kernel(self) -> None:
        if (
            isinstance(self.kernel_task, mp.Process)
            and self.kernel_task.pid is not None
        ):
            LOGGER.debug("Sending SIGINT to kernel")
            os.kill(self.kernel_task.pid, signal.SIGINT)

    def close_kernel(self) -> None:
        assert self.kernel_task is not None, "kernel not started"

        if isinstance(self.kernel_task, mp.Process):
            self.queue_manager.close_queues()
            if self.kernel_task.is_alive():
                self.kernel_task.terminate()
            self.kernel_connection.close()
        elif self.kernel_task.is_alive():
            # We don't join the kernel thread because we don't want to server
            # to block on it finishing
            self.queue_manager.control_queue.put(requests.StopRequest())

    @property
    def kernel_connection(self) -> connection.Connection:
        assert self._read_conn is not None, "connection not started"
        return self._read_conn


class Session:
    """A client session.

    Each session has its own Python kernel, for editing and running the app,
    and its own websocket, for sending messages to the client.
    """

    TTL_SECONDS = 120

    @classmethod
    def create(
        cls,
        session_handler: SessionHandler,
        mode: SessionMode,
        app: InternalApp,
        app_metadata: AppMetadata,
    ) -> Session:
        configs = app.cell_manager.config_map()
        use_multiprocessing = mode == SessionMode.EDIT
        queue_manager = QueueManager(use_multiprocessing)
        kernel_manager = KernelManager(
            queue_manager, mode, configs, app_metadata
        )
        return cls(session_handler, queue_manager, kernel_manager)

    def __init__(
        self,
        session_handler: SessionHandler,
        queue_manager: QueueManager,
        kernel_manager: KernelManager,
    ) -> None:
        """Initialize kernel and client connection to it."""
        self._queue_manager: QueueManager
        self.session_handler = session_handler
        self._queue_manager = queue_manager
        self.kernel_manager = kernel_manager
        self.kernel_manager.start_kernel()

        def check_alive() -> None:
            if not self.kernel_manager.is_alive():
                self.close()
                print()
                print_tabbed(
                    "\033[31mThe Python kernel died unexpectedly.\033[0m"
                )
                print()
                sys.exit()

        self.check_alive = check_alive
        self.session_handler.on_start(
            connection=self.kernel_manager.kernel_connection,
            check_alive=check_alive,
        )

    def try_interrupt(self) -> None:
        self.kernel_manager.interrupt_kernel()

    def put_request(self, request: requests.Request) -> None:
        self._queue_manager.control_queue.put(request)

    def put_input(self, text: str) -> None:
        self._queue_manager.input_queue.put(text)

    def close(self) -> None:
        self.session_handler.on_stop(self.kernel_manager.kernel_connection)
        self.kernel_manager.close_kernel()


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
        self.app_config: _AppConfig
        self.include_code = include_code

        self.app = self.load_app()
        self.app_config = self.app.config

        self.app_metadata = AppMetadata(
            filename=self._get_filename(),
        )

        if mode == SessionMode.EDIT:
            # In edit mode, the server gets a random token to prevent
            # frontends that it didn't create from connecting to it and
            # executing edit-only commands (such as overwriting the file).
            self.server_token = str(uuid4())
        else:
            # Because run-mode is read-only, all that matters is that
            # the frontend's app matches the server's app.
            self.server_token = str(
                hash("".join(code for code in self.app.cell_manager.codes()))
            )

    def load_app(self) -> InternalApp:
        """
        Load the app from the current file.
        Otherwise, return an empty app.
        """
        app = codegen.get_app(self.filename)
        if app is None:
            empty_app = InternalApp(App())
            empty_app.cell_manager.register_cell(
                cell_id=None,
                code="",
                config=CellConfig(),
            )
            return empty_app

        return InternalApp(app)

    def update_app_config(self, config: dict[str, Any]) -> None:
        self.app_config.update(config)

    def rename(self, filename: Optional[str]) -> None:
        """Register a change in filename.

        Should be called if an api call renamed the current file on disk.
        """
        self.filename = filename
        self.app_metadata.filename = self._get_filename()

    def create_session(
        self, session_id: str, session_handler: SessionHandler
    ) -> Session:
        """Create a new session"""
        LOGGER.debug("creating new session for id %s", session_id)
        if session_id not in self.sessions:
            s = Session.create(
                session_handler=session_handler,
                mode=self.mode,
                app=self.load_app(),
                app_metadata=self.app_metadata,
            )
            self.sessions[session_id] = s
            return s
        else:
            return self.sessions[session_id]

    def _get_filename(self) -> Optional[str]:
        if self.filename is None:
            return None
        try:
            return os.path.abspath(self.filename)
        except AttributeError:
            return None

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
        LOGGER.debug("Closed all sessions.")
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
