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
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from marimo import _loggers
from marimo._ast import codegen
from marimo._ast.app import App, InternalApp
from marimo._ast.cell import CellConfig, CellId_t
from marimo._messaging.ops import Alert, MessageOperation, Reload
from marimo._messaging.types import KernelMessage
from marimo._output.formatters.formatters import register_formatters
from marimo._runtime import requests, runtime
from marimo._runtime.requests import AppMetadata
from marimo._server.model import (
    ConnectionState,
    SessionConsumer,
    SessionMode,
)
from marimo._server.session.session_view import SessionView
from marimo._server.types import QueueType
from marimo._server.utils import import_files, print_tabbed
from marimo._utils.disposable import Disposable
from marimo._utils.distributor import Distributor
from marimo._utils.file_watcher import FileWatcher
from marimo._utils.repr import format_repr
from marimo._utils.typed_connection import TypedConnection

LOGGER = _loggers.marimo_logger()
SESSION_MANAGER: Optional["SessionManager"] = None

SessionId = str


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
        self.app_metadata = app_metadata
        self._read_conn: Optional[TypedConnection[KernelMessage]] = None

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
                if not self.kernel_connection.closed:
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
        self._read_conn = TypedConnection[KernelMessage].of(listener.accept())

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
    def kernel_connection(self) -> TypedConnection[KernelMessage]:
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
        session_consumer: SessionConsumer,
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
        return cls(app, session_consumer, queue_manager, kernel_manager)

    def __init__(
        self,
        app: InternalApp,
        session_consumer: SessionConsumer,
        queue_manager: QueueManager,
        kernel_manager: KernelManager,
    ) -> None:
        """Initialize kernel and client connection to it."""
        self._queue_manager: QueueManager
        self.app = app
        # This can be optional in case a consumer gets disconnected,
        # and we want to continue the session without a consumer.
        self.session_consumer: Optional[SessionConsumer] = None
        self._queue_manager = queue_manager
        self.kernel_manager = kernel_manager
        self.session_view = SessionView()

        self.kernel_manager.start_kernel()
        # Reads from the kernel connection and distributes the
        # messages to each subscriber.
        self.message_distributor = Distributor[KernelMessage](
            self.kernel_manager.kernel_connection
        )
        self.message_distributor.add_consumer(
            lambda msg: self.session_view.add_raw_operation(msg[1])
        )
        self.connect_consumer(session_consumer)
        self.message_distributor.start()

    def _check_alive(self) -> None:
        if not self.kernel_manager.is_alive():
            LOGGER.debug("Closing session because kernel died")
            self.close()
            print()
            print_tabbed("\033[31mThe Python kernel died unexpectedly.\033[0m")
            print()
            sys.exit()

    def try_interrupt(self) -> None:
        self.kernel_manager.interrupt_kernel()

    def put_request(self, request: requests.Request) -> None:
        self._queue_manager.control_queue.put(request)
        self.session_view.add_request(request)

    def put_input(self, text: str) -> None:
        self._queue_manager.input_queue.put(text)
        self.session_view.add_stdin(text)

    def disconnect_consumer(self) -> None:
        """Stop the session consumer but keep the kernel running"""
        assert (
            self.session_consumer is not None
        ), "Expecting a session consumer to pause"
        LOGGER.debug("Disconnecting session consumer")
        self.session_consumer.on_stop()
        self.unsubscribe_consumer()
        self.session_consumer = None

    def connect_consumer(self, session_consumer: SessionConsumer) -> None:
        """Connect or resume the session with a new consumer"""
        assert (
            self.session_consumer is None
        ), "Expecting no existing session consumer"

        self.session_consumer = session_consumer

        subscribe = self.session_consumer.on_start(self._check_alive)
        self.unsubscribe_consumer = self.message_distributor.add_consumer(
            subscribe
        )

    def get_current_state(self) -> SessionView:
        return self.session_view

    def connection_state(self) -> ConnectionState:
        if self.session_consumer is None:
            return ConnectionState.ORPHANED
        return self.session_consumer.connection_state()

    async def write_operation(self, operation: MessageOperation) -> None:
        self.session_view.add_operation(operation)
        if self.session_consumer is not None:
            await self.session_consumer.write_operation(operation)

    def close(self) -> None:
        # Could be no consumer if we already disconnect, but the session
        # is running in the background
        if self.session_consumer is not None:
            self.session_consumer.on_stop()
        self.message_distributor.stop()
        self.kernel_manager.close_kernel()
        self.unsubscribe_consumer()

    def __repr__(self) -> str:
        return format_repr(
            self,
            {
                "connection_state": self.connection_state(),
                "consumer": self.session_consumer,
            },
        )


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
        development_mode: bool,
        quiet: bool,
        include_code: bool,
        lsp_server: LspServer,
    ) -> None:
        self.filename = filename
        self.mode = mode
        self.development_mode = development_mode
        self.quiet = quiet
        self.sessions: dict[str, Session] = {}
        self.include_code = include_code
        self.lsp_server = lsp_server
        self.watcher: Optional[FileWatcher] = None

        app = self.load_app()
        self.app_config = app.config

        self.app_metadata = AppMetadata(
            filename=self._get_file_path(),
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
                hash("".join(code for code in app.cell_manager.codes()))
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

        Should be called if an api call renamed the current file on disk,
        or opened another file.
        """
        self.filename = filename
        self.app_metadata.filename = self._get_file_path()

    def create_session(
        self, session_id: SessionId, session_consumer: SessionConsumer
    ) -> Session:
        """Create a new session"""
        LOGGER.debug("Creating new session for id %s", session_id)
        if session_id not in self.sessions:
            self.sessions[session_id] = Session.create(
                session_consumer=session_consumer,
                mode=self.mode,
                # When we create a session,
                # we load the app from the file
                app=self.load_app(),
                app_metadata=self.app_metadata,
            )
        return self.sessions[session_id]

    def get_session(self, session_id: SessionId) -> Optional[Session]:
        return self.sessions.get(session_id)

    def maybe_resume_session(
        self, new_session_id: SessionId
    ) -> Optional[Session]:
        """
        Try to resume a session if one is resumable.
        If it is resumable, return the session and update the session id.
        """

        # If in run mode, only resume the session if it is orphaned and has
        # the same session id, otherwise we want to create a new session
        if self.mode == SessionMode.RUN:
            maybe_session = self.get_session(new_session_id)
            if (
                maybe_session
                and maybe_session.connection_state()
                == ConnectionState.ORPHANED
            ):
                LOGGER.debug(
                    "Found a resumable RUN session: prev_id=%s",
                    new_session_id,
                )
                return maybe_session
            return None

        if len(self.sessions) == 0:
            return None
        if len(self.sessions) > 1:
            raise Exception("Only one session should exist while editing")

        # Should only return an orphaned session
        (session_id, session) = list(self.sessions.items())[0]
        connection_state = session.connection_state()
        if connection_state == ConnectionState.ORPHANED:
            LOGGER.debug(
                f"Found a resumable EDIT session: prev_id={session_id}"
            )
            # Set new session and remove old session
            self.sessions[new_session_id] = session
            # If the ID is the same, we don't need to delete the old session
            if new_session_id != session_id:
                del self.sessions[session_id]
            return session

        LOGGER.debug(
            "Session is not resumable, current state: %s",
            connection_state,
        )
        return None

    def _get_file_path(self) -> Optional[str]:
        if self.filename is None:
            return None
        try:
            return os.path.abspath(self.filename)
        except AttributeError:
            return None

    def any_clients_connected(self) -> bool:
        """Returns True if at least one client has an open socket."""
        for session in self.sessions.values():
            if session.connection_state() == ConnectionState.OPEN:
                return True
        return False

    async def start_lsp_server(self) -> None:
        """Starts the lsp server if it is not already started.

        Doesn't start in run mode.
        """
        if self.mode == SessionMode.RUN:
            LOGGER.warn("Cannot start LSP server in run mode")
            return

        alert = self.lsp_server.start()

        if alert is not None:
            for _, session in self.sessions.items():
                await session.write_operation(alert)
            return

    def close_session(self, session_id: SessionId) -> None:
        LOGGER.debug("Closing session %s", session_id)
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
        self.lsp_server.stop()
        if self.watcher:
            self.watcher.stop()

    def should_send_code_to_frontend(self) -> bool:
        """Returns True if the server can send messages to the frontend."""
        return self.mode == SessionMode.EDIT or self.include_code

    def start_file_watcher(self) -> Disposable:
        """Starts the file watcher if it is not already started"""
        if self.mode == SessionMode.EDIT:
            # We don't support file watching in edit mode yet
            # as there are some edge cases that would need to be handled.
            # - what to do if the file is deleted, or is renamed
            # - do we re-run the app or just show the changed code
            # - we don't properly handle saving from the frontend
            LOGGER.warn("Cannot start file watcher in edit mode")
            return Disposable.empty()

        file_path = self._get_file_path()
        if file_path is None:
            LOGGER.warn("Cannot start file watcher without a filename")
            return Disposable.empty()

        async def on_file_changed(path: Path) -> None:
            LOGGER.debug(f"{path} was modified")
            for _, session in self.sessions.items():
                session.app = self.load_app()
                await session.write_operation(Reload())

        LOGGER.debug("Starting file watcher for %s", file_path)
        self.watcher = FileWatcher.create(Path(file_path), on_file_changed)
        self.watcher.start()
        return Disposable(self.watcher.stop)


class LspServer:
    def __init__(self, port: int) -> None:
        self.port = port
        self.process: Optional[subprocess.Popen[bytes]] = None

    def start(self) -> Optional[Alert]:
        if self.process is not None:
            LOGGER.debug("LSP server already started")
            return None

        binpath = shutil.which("node")
        if binpath is None:
            LOGGER.error("Node.js not found; cannot start LSP server.")
            return Alert(
                title="Github Copilot: Connection Error",
                description="<span><a class='hyperlink' href='https://docs.marimo.io/getting_started/index.html#github-copilot'>Install Node.js</a> to use copilot.</span>",  # noqa: E501
                variant="danger",
            )

        cmd = None
        try:
            LOGGER.debug("Starting LSP server at port %s...", self.port)
            lsp_bin = os.path.join(
                str(import_files("marimo").joinpath("_lsp")),
                "index.js",
            )
            cmd = f"node {lsp_bin} --port {self.port}"
            LOGGER.debug("... running command: %s", cmd)
            self.process = subprocess.Popen(
                cmd.split(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            LOGGER.debug(
                "... node process return code (`None` means success): %s",
                self.process.returncode,
            )
            LOGGER.debug("Started LSP server at port %s", self.port)
        except Exception as e:
            LOGGER.error(
                "When starting language server (%s), got error: %s",
                cmd,
                e,
            )
            self.process = None

        return None

    def is_running(self) -> bool:
        return self.process is not None

    def stop(self) -> None:
        if self.process is not None:
            self.process.terminate()
            self.process = None
            LOGGER.debug("Stopped LSP server at port %s", self.port)
        else:
            LOGGER.debug("LSP server not running")


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
        development_mode=development_mode,
        quiet=quiet,
        include_code=include_code,
        lsp_server=LspServer(port * 10),
    )
    return SESSION_MANAGER


def get_manager() -> SessionManager:
    """Cannot be called until manager has been initialized."""
    assert SESSION_MANAGER is not None
    return SESSION_MANAGER
