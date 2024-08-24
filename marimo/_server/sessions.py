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

import asyncio
import multiprocessing as mp
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
from multiprocessing import connection
from multiprocessing.queues import Queue as MPQueue
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from marimo import _loggers
from marimo._ast.cell import CellConfig, CellId_t
from marimo._cli.print import red
from marimo._config.manager import UserConfigManager
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._messaging.ops import (
    Alert,
    FocusCell,
    MessageOperation,
    Reload,
    UpdateCellCodes,
)
from marimo._messaging.types import KernelMessage
from marimo._output.formatters.formatters import register_formatters
from marimo._runtime import requests, runtime
from marimo._runtime.requests import (
    AppMetadata,
    CreationRequest,
    ExecuteMultipleRequest,
    ExecutionRequest,
    SerializedCLIArgs,
    SerializedQueryParams,
    SetUIElementValueRequest,
)
from marimo._server.exceptions import InvalidSessionException
from marimo._server.file_manager import AppFileManager
from marimo._server.file_router import AppFileRouter, MarimoFileKey
from marimo._server.ids import ConsumerId, SessionId
from marimo._server.model import ConnectionState, SessionConsumer, SessionMode
from marimo._server.models.models import InstantiateRequest
from marimo._server.recents import RecentFilesManager
from marimo._server.session.session_view import SessionView
from marimo._server.tokens import AuthToken, SkewProtectionToken
from marimo._server.types import QueueType
from marimo._server.utils import print_tabbed
from marimo._tracer import server_tracer
from marimo._utils.disposable import Disposable
from marimo._utils.distributor import Distributor
from marimo._utils.file_watcher import FileWatcher
from marimo._utils.paths import import_files
from marimo._utils.repr import format_repr
from marimo._utils.typed_connection import TypedConnection

LOGGER = _loggers.marimo_logger()
SESSION_MANAGER: Optional["SessionManager"] = None


class QueueManager:
    """Manages queues for a session."""

    def __init__(self, use_multiprocessing: bool):
        context = mp.get_context("spawn") if use_multiprocessing else None

        # Control messages for the kernel (run, set UI element, set config, etc
        # ) are sent through the control queue
        self.control_queue: QueueType[requests.ControlRequest] = (
            context.Queue() if context is not None else queue.Queue()
        )

        # Set UI element queues are stored in both the control queue and
        # this queue, so that the backend can merge/batch set-ui-element
        # requests.
        self.set_ui_element_queue: QueueType[
            requests.SetUIElementValueRequest
        ] = context.Queue() if context is not None else queue.Queue()

        # Code completion requests are sent through a separate queue
        self.completion_queue: QueueType[requests.CodeCompletionRequest] = (
            context.Queue() if context is not None else queue.Queue()
        )

        self.win32_interrupt_queue: QueueType[bool] | None
        if sys.platform == "win32":
            self.win32_interrupt_queue = (
                context.Queue() if context is not None else queue.Queue()
            )
        else:
            self.win32_interrupt_queue = None

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

        if isinstance(self.set_ui_element_queue, MPQueue):
            self.set_ui_element_queue.cancel_join_thread()
            self.set_ui_element_queue.close()

        if isinstance(self.input_queue, MPQueue):
            # again, don't make the child process wait for the queues to empty
            self.input_queue.cancel_join_thread()
            self.input_queue.close()

        if isinstance(self.completion_queue, MPQueue):
            self.completion_queue.cancel_join_thread()
            self.completion_queue.close()

        if isinstance(self.win32_interrupt_queue, MPQueue):
            self.win32_interrupt_queue.cancel_join_thread()
            self.win32_interrupt_queue.close()


class KernelManager:
    def __init__(
        self,
        queue_manager: QueueManager,
        mode: SessionMode,
        configs: dict[CellId_t, CellConfig],
        app_metadata: AppMetadata,
        user_config_manager: UserConfigManager,
        virtual_files_supported: bool,
        redirect_console_to_browser: bool = False,
    ) -> None:
        self.kernel_task: Optional[threading.Thread] | Optional[mp.Process]
        self.queue_manager = queue_manager
        self.mode = mode
        self.configs = configs
        self.app_metadata = app_metadata
        self.user_config_manager = user_config_manager
        self.redirect_console_to_browser = redirect_console_to_browser
        self._read_conn: Optional[TypedConnection[KernelMessage]] = None
        self._virtual_files_supported = virtual_files_supported

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
                    self.queue_manager.set_ui_element_queue,
                    self.queue_manager.completion_queue,
                    self.queue_manager.input_queue,
                    listener.address,
                    is_edit_mode,
                    self.configs,
                    self.app_metadata,
                    self.user_config_manager.config,
                    self._virtual_files_supported,
                    self.redirect_console_to_browser,
                    self.queue_manager.win32_interrupt_queue,
                    self.profile_path,
                    GLOBAL_SETTINGS.LOG_LEVEL,
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
                    self.queue_manager.set_ui_element_queue,
                    self.queue_manager.completion_queue,
                    self.queue_manager.input_queue,
                    listener.address,
                    is_edit_mode,
                    self.configs,
                    self.app_metadata,
                    self.user_config_manager.config,
                    self._virtual_files_supported,
                    self.redirect_console_to_browser,
                    # win32 interrupt queue
                    None,
                    # profile path
                    None,
                    # log level
                    GLOBAL_SETTINGS.LOG_LEVEL,
                ),
                # daemon threads can create child processes, unlike
                # daemon processes
                daemon=True,
            )

        self.kernel_task.start()  # type: ignore
        # First thing kernel does is connect to the socket, so it's safe to
        # call accept
        self._read_conn = TypedConnection[KernelMessage].of(listener.accept())

    @property
    def profile_path(self) -> str | None:
        self._profile_path: str | None

        if hasattr(self, "_profile_path"):
            return self._profile_path

        profile_dir = GLOBAL_SETTINGS.PROFILE_DIR
        if profile_dir is not None:
            self._profile_path = os.path.join(
                profile_dir,
                (
                    os.path.basename(self.app_metadata.filename) + str(uuid4())
                    if self.app_metadata.filename is not None
                    else str(uuid4())
                ),
            )
        else:
            self._profile_path = None
        return self._profile_path

    def is_alive(self) -> bool:
        return self.kernel_task is not None and self.kernel_task.is_alive()

    def interrupt_kernel(self) -> None:
        if (
            isinstance(self.kernel_task, mp.Process)
            and self.kernel_task.pid is not None
        ):
            q = self.queue_manager.win32_interrupt_queue
            if sys.platform == "win32" and q is not None:
                LOGGER.debug("Queueing interrupt request for kernel.")
                q.put_nowait(True)
            else:
                LOGGER.debug("Sending SIGINT to kernel")
                os.kill(self.kernel_task.pid, signal.SIGINT)

    def close_kernel(self) -> None:
        assert self.kernel_task is not None, "kernel not started"

        if isinstance(self.kernel_task, mp.Process):
            if self.profile_path is not None and self.kernel_task.is_alive():
                self.queue_manager.control_queue.put(requests.StopRequest())
                # Hack: Wait for kernel to exit and write out profile;
                # joining the process hangs, but not sure why.
                print(
                    "\tWriting profile statistics to",
                    self.profile_path,
                    " ...",
                )
                while not os.path.exists(self.profile_path):
                    time.sleep(0.1)
                time.sleep(1)

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


class Room:
    """
    A room is a collection of SessionConsumers
    that can be used to broadcast messages to all
    of them.
    """

    def __init__(self) -> None:
        self.main_consumer: Optional[SessionConsumer] = None
        self.consumers: Dict[SessionConsumer, ConsumerId] = {}
        self.disposables: Dict[SessionConsumer, Disposable] = {}

    def add_consumer(
        self,
        consumer: SessionConsumer,
        dispose: Disposable,
        consumer_id: ConsumerId,
        # Whether the consumer is the main session consumer
        # We only allow one main consumer, the rest are kiosk consumers
        main: bool,
    ) -> None:
        self.consumers[consumer] = consumer_id
        self.disposables[consumer] = dispose
        if main:
            assert (
                self.main_consumer is None
            ), "Main session consumer already exists"
            self.main_consumer = consumer

    def remove_consumer(self, consumer: SessionConsumer) -> None:
        if consumer not in self.consumers:
            LOGGER.debug(
                "Attempted to remove a consumer that was not in room."
            )
            return

        if consumer == self.main_consumer:
            self.main_consumer = None
        self.consumers.pop(consumer)
        disposable = self.disposables.pop(consumer)
        try:
            consumer.on_stop()
        finally:
            disposable.dispose()

    def broadcast(self, operation: MessageOperation) -> None:
        for consumer in self.consumers:
            consumer.write_operation(operation)

    def close(self) -> None:
        for consumer in self.consumers:
            disposable = self.disposables.pop(consumer)
            consumer.on_stop()
            disposable.dispose()
        self.consumers = {}
        self.main_consumer = None


class Session:
    """A client session.

    Each session has its own Python kernel, for editing and running the app,
    and its own websocket, for sending messages to the client.
    """

    TTL_SECONDS = 120

    @classmethod
    def create(
        cls,
        initialization_id: str,
        session_consumer: SessionConsumer,
        mode: SessionMode,
        app_metadata: AppMetadata,
        app_file_manager: AppFileManager,
        user_config_manager: UserConfigManager,
        virtual_files_supported: bool,
        redirect_console_to_browser: bool = False,
    ) -> Session:
        """
        Create a new session.
        """
        configs = app_file_manager.app.cell_manager.config_map()
        use_multiprocessing = mode == SessionMode.EDIT
        queue_manager = QueueManager(use_multiprocessing)
        kernel_manager = KernelManager(
            queue_manager,
            mode,
            configs,
            app_metadata,
            user_config_manager,
            virtual_files_supported=virtual_files_supported,
            redirect_console_to_browser=redirect_console_to_browser,
        )
        return cls(
            initialization_id,
            session_consumer,
            queue_manager,
            kernel_manager,
            app_file_manager,
        )

    def __init__(
        self,
        initialization_id: str,
        session_consumer: SessionConsumer,
        queue_manager: QueueManager,
        kernel_manager: KernelManager,
        app_file_manager: AppFileManager,
    ) -> None:
        """Initialize kernel and client connection to it."""
        # This is some unique ID that we can use to identify the session
        # We don't use the session_id because this can change if the
        # session is resumed
        self.initialization_id = initialization_id
        self._queue_manager: QueueManager
        self.app_file_manager = app_file_manager
        self.room = Room()
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
        self.connect_consumer(session_consumer, main=True)

        self.message_distributor.start()
        self.heartbeat_task: Optional[asyncio.Task[Any]] = None
        self._start_heartbeat()
        self._closed = False

    def _start_heartbeat(self) -> None:
        def _check_alive() -> None:
            if not self.kernel_manager.is_alive():
                LOGGER.debug("Closing session because kernel died")
                self.close()
                print()
                print_tabbed(red("The Python kernel died unexpectedly."))
                print()
                sys.exit()

        # Start a heartbeat task, which checks if the kernel is alive
        # every second

        async def _heartbeat() -> None:
            while True:
                await asyncio.sleep(1)
                _check_alive()

        try:
            loop = asyncio.get_event_loop()
            self.heartbeat_task = loop.create_task(_heartbeat())
        except RuntimeError:
            # This can happen if there is no event loop running
            self.heartbeat_task = None

    def try_interrupt(self) -> None:
        """Try to interrupt the kernel."""
        self.kernel_manager.interrupt_kernel()

    def put_control_request(self, request: requests.ControlRequest) -> None:
        """Put a control request in the control queue."""
        self._queue_manager.control_queue.put(request)
        if isinstance(request, SetUIElementValueRequest):
            self._queue_manager.set_ui_element_queue.put(request)
        # Propagate the control request to the room
        if isinstance(request, ExecuteMultipleRequest):
            self.room.broadcast(
                UpdateCellCodes(
                    cell_ids=request.cell_ids,
                    codes=request.codes,
                )
            )
            if len(request.cell_ids) == 1:
                self.room.broadcast(FocusCell(cell_id=request.cell_ids[0]))
        self.session_view.add_control_request(request)

    def put_completion_request(
        self, request: requests.CodeCompletionRequest
    ) -> None:
        """Put a code completion request in the completion queue."""
        self._queue_manager.completion_queue.put(request)

    def put_input(self, text: str) -> None:
        """Put an input() request in the input queue."""
        self._queue_manager.input_queue.put(text)
        self.session_view.add_stdin(text)

    def disconnect_consumer(self, session_consumer: SessionConsumer) -> None:
        """
        Stop the session consumer but keep the kernel running.

        This will disconnect the main session consumer,
        or a kiosk consumer.
        """
        self.room.remove_consumer(session_consumer)

    def maybe_disconnect_consumer(self) -> None:
        """
        Disconnect the main session consumer if it connected.
        """
        if self.room.main_consumer is not None:
            self.disconnect_consumer(self.room.main_consumer)

    def connect_consumer(
        self, session_consumer: SessionConsumer, *, main: bool
    ) -> None:
        """
        Connect or resume the session with a new consumer.

        If its the main consumer and one already exists,
        an exception is raised.
        """
        subscribe = session_consumer.on_start()
        unsubscribe_consumer = self.message_distributor.add_consumer(subscribe)
        self.room.add_consumer(
            session_consumer,
            unsubscribe_consumer,
            session_consumer.consumer_id,
            main=main,
        )

    def get_current_state(self) -> SessionView:
        """Return the current state of the session."""
        return self.session_view

    def connection_state(self) -> ConnectionState:
        """Return the connection state of the session."""
        if self._closed:
            return ConnectionState.CLOSED
        if self.room.main_consumer is None:
            return ConnectionState.ORPHANED
        return self.room.main_consumer.connection_state()

    def write_operation(self, operation: MessageOperation) -> None:
        """Write an operation to the session consumer and the session view."""
        self.session_view.add_operation(operation)
        self.room.broadcast(operation)

    def close(self) -> None:
        """
        Close the session.

        This will close the session consumer, kernel, and all kiosk consumers.
        """
        self._closed = True
        # Close the room
        self.room.close()
        # Close the kernel
        self.message_distributor.stop()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        self.kernel_manager.close_kernel()

    def instantiate(self, request: InstantiateRequest) -> None:
        """Instantiate the app."""
        execution_requests = tuple(
            ExecutionRequest(cell_id=cell_data.cell_id, code=cell_data.code)
            for cell_data in self.app_file_manager.app.cell_manager.cell_data()
        )

        self.put_control_request(
            CreationRequest(
                execution_requests=execution_requests,
                set_ui_element_value_request=SetUIElementValueRequest(
                    object_ids=request.object_ids,
                    values=request.values,
                    token=str(uuid4()),
                ),
            )
        )

    def __repr__(self) -> str:
        return format_repr(
            self,
            {
                "connection_state": self.connection_state(),
                "room": self.room,
            },
        )


class SessionManager:
    """Mapping from client session IDs to sessions.

    Maintains a mapping from client session IDs to client sessions;
    there is exactly one session per client.

    The SessionManager also encapsulates state common to all sessions:
    - the app filename
    - the app mode (edit or run)
    - the auth token
    - the skew-protection token
    """

    def __init__(
        self,
        file_router: AppFileRouter,
        mode: SessionMode,
        development_mode: bool,
        quiet: bool,
        include_code: bool,
        lsp_server: LspServer,
        user_config_manager: UserConfigManager,
        cli_args: SerializedCLIArgs,
        auth_token: Optional[AuthToken],
        redirect_console_to_browser: bool = False,
    ) -> None:
        self.file_router = file_router
        self.mode = mode
        self.development_mode = development_mode
        self.quiet = quiet
        self.sessions: dict[SessionId, Session] = {}
        self.include_code = include_code
        self.lsp_server = lsp_server
        self.watcher: Optional[FileWatcher] = None
        self.recents = RecentFilesManager()
        self.user_config_manager = user_config_manager
        self.cli_args = cli_args
        self.redirect_console_to_browser = redirect_console_to_browser

        # Auth token and Skew-protection token
        if auth_token is not None:
            self.auth_token = auth_token
            self.skew_protection_token = SkewProtectionToken.random()
        elif mode == SessionMode.EDIT:
            # In edit mode, if no auth token is provided,
            # generate a random token
            self.auth_token = AuthToken.random()
            self.skew_protection_token = SkewProtectionToken.random()
        else:
            app = file_router.get_single_app_file_manager(
                default_width=user_config_manager.get_config()["display"][
                    "default_width"
                ]
            ).app
            codes = "".join(code for code in app.cell_manager.codes())
            # Because run-mode is read-only and we could have multiple
            # servers for the same app (going to sleep or autoscaling),
            # we default to a token based on the app's code
            self.auth_token = AuthToken.from_code(codes)
            self.skew_protection_token = SkewProtectionToken.from_code(codes)

    def app_manager(self, key: MarimoFileKey) -> AppFileManager:
        """
        Get the app manager for the given key.
        """
        return self.file_router.get_file_manager(
            key,
            default_width=self.user_config_manager.get_config()["display"][
                "default_width"
            ],
        )

    def create_session(
        self,
        session_id: SessionId,
        session_consumer: SessionConsumer,
        query_params: SerializedQueryParams,
        file_key: MarimoFileKey,
    ) -> Session:
        """Create a new session"""
        LOGGER.debug("Creating new session for id %s", session_id)
        if session_id not in self.sessions:
            app_file_manager = self.file_router.get_file_manager(
                file_key,
                default_width=self.user_config_manager.get_config()["display"][
                    "default_width"
                ],
            )

            if app_file_manager.path:
                self.recents.touch(app_file_manager.path)

            self.sessions[session_id] = Session.create(
                initialization_id=file_key,
                session_consumer=session_consumer,
                mode=self.mode,
                app_metadata=AppMetadata(
                    query_params=query_params,
                    filename=app_file_manager.path,
                    cli_args=self.cli_args,
                ),
                app_file_manager=app_file_manager,
                user_config_manager=self.user_config_manager,
                virtual_files_supported=True,
                redirect_console_to_browser=self.redirect_console_to_browser,
            )
        return self.sessions[session_id]

    def get_session(self, session_id: SessionId) -> Optional[Session]:
        session = self.sessions.get(session_id)
        if session:
            return session

        # Search for kiosk sessions
        for session in self.sessions.values():
            if session_id in session.room.consumers.values():
                return session

        return None

    def get_session_by_file_key(
        self, file_key: MarimoFileKey
    ) -> Optional[Session]:
        for session in self.sessions.values():
            if session.initialization_id == file_key:
                return session
        return None

    def maybe_resume_session(
        self, new_session_id: SessionId, file_key: MarimoFileKey
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

        # Should only return an orphaned session
        sessions_with_the_same_file: dict[SessionId, Session] = {
            session_id: session
            for session_id, session in self.sessions.items()
            if session.app_file_manager.path == os.path.abspath(file_key)
        }

        if len(sessions_with_the_same_file) == 0:
            return None
        if len(sessions_with_the_same_file) > 1:
            raise InvalidSessionException(
                "Only one session should exist while editing"
            )

        (session_id, session) = next(iter(sessions_with_the_same_file.items()))
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

    def any_clients_connected(self, key: MarimoFileKey) -> bool:
        """Returns True if at least one client has an open socket."""
        if key.startswith(AppFileRouter.NEW_FILE):
            return False

        for session in self.sessions.values():
            if session.connection_state() == ConnectionState.OPEN and (
                session.app_file_manager.path == os.path.abspath(key)
            ):
                return True
        return False

    def get_session_for_key(self, key: MarimoFileKey) -> Optional[Session]:
        for session in self.sessions.values():
            if (
                session.app_file_manager.path == os.path.abspath(key)
                or session.initialization_id == key
            ) and session.connection_state() == ConnectionState.OPEN:
                return session
        return None

    async def start_lsp_server(self) -> None:
        """Starts the lsp server if it is not already started.

        Doesn't start in run mode.
        """
        if self.mode == SessionMode.RUN:
            LOGGER.warning("Cannot start LSP server in run mode")
            return

        alert = self.lsp_server.start()

        if alert is not None:
            for _, session in self.sessions.items():
                session.write_operation(alert)
            return

    def close_session(self, session_id: SessionId) -> bool:
        LOGGER.debug("Closing session %s", session_id)
        session = self.get_session(session_id)
        if session is not None:
            session.close()
            del self.sessions[session_id]
            return True
        return False

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
            LOGGER.warning("Cannot start file watcher in edit mode")
            return Disposable.empty()
        file = self.file_router.maybe_get_single_file()
        if not file:
            return Disposable.empty()

        file_path = file.path

        async def on_file_changed(path: Path) -> None:
            LOGGER.debug(f"{path} was modified")
            for _, session in self.sessions.items():
                session.app_file_manager.reload()
                session.write_operation(Reload())

        LOGGER.debug("Starting file watcher for %s", file_path)
        self.watcher = FileWatcher.create(Path(file_path), on_file_changed)
        self.watcher.start()
        return Disposable(self.watcher.stop)


class LspServer:
    def __init__(self, port: int) -> None:
        self.port = port
        self.process: Optional[subprocess.Popen[bytes]] = None

    @server_tracer.start_as_current_span("lsp_server.start")
    def start(self) -> Optional[Alert]:
        if self.process is not None:
            LOGGER.debug("LSP server already started")
            return None

        binpath = shutil.which("node")
        if binpath is None:
            LOGGER.error("Node.js not found; cannot start LSP server.")
            return Alert(
                title="GitHub Copilot: Connection Error",
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


class NoopLspServer(LspServer):
    def __init__(self) -> None:
        super().__init__(0)

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass
