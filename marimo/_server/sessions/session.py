# Copyright 2024 Marimo. All rights reserved.
"""Core Session class for managing client sessions.

Each session represents a single client connection with its own Python kernel
and websocket for bidirectional communication.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

from marimo import _loggers
from marimo._cli.print import red
from marimo._config.manager import MarimoConfigManager, ScriptConfigManager
from marimo._messaging.ops import (
    FocusCell,
    MessageOperation,
    UpdateCellCodes,
)
from marimo._messaging.types import KernelMessage
from marimo._runtime import requests
from marimo._runtime.requests import (
    AppMetadata,
    CreationRequest,
    ExecuteMultipleRequest,
    ExecutionRequest,
    HTTPRequest,
    SetUIElementValueRequest,
    SyncGraphRequest,
)
from marimo._server.model import ConnectionState, SessionConsumer, SessionMode
from marimo._server.models.models import InstantiateRequest
from marimo._server.notebook import AppFileManager
from marimo._server.session.serialize import (
    SessionCacheKey,
    SessionCacheManager,
)
from marimo._server.session.session_view import SessionView
from marimo._server.sessions.managers import (
    KernelManagerImpl,
    QueueManagerImpl,
)
from marimo._server.sessions.room import Room
from marimo._server.sessions.types import KernelManager, QueueManager, Session
from marimo._server.utils import print_, print_tabbed
from marimo._types.ids import ConsumerId
from marimo._utils.distributor import (
    ConnectionDistributor,
    QueueDistributor,
)
from marimo._utils.repr import format_repr

if TYPE_CHECKING:
    from collections.abc import Mapping

LOGGER = _loggers.marimo_logger()

_DEFAULT_TTL_SECONDS = 120

__all__ = ["Session", "SessionImpl"]


class SessionImpl(Session):
    """A client session.

    Each session has its own Python kernel, for editing and running the app,
    and its own websocket, for sending messages to the client.
    """

    SESSION_CACHE_INTERVAL_SECONDS = 2

    @classmethod
    def create(
        cls,
        *,
        initialization_id: str,
        session_consumer: SessionConsumer,
        mode: SessionMode,
        app_metadata: AppMetadata,
        app_file_manager: AppFileManager,
        config_manager: MarimoConfigManager,
        virtual_files_supported: bool,
        redirect_console_to_browser: bool,
        ttl_seconds: Optional[int],
    ) -> Session:
        """
        Create a new session.
        """
        # Inherit config from the session manager
        # and override with any script-level config
        config_manager = config_manager.with_overrides(
            ScriptConfigManager(app_file_manager.path).get_config()
        )

        configs = app_file_manager.app.cell_manager.config_map()
        use_multiprocessing = mode == SessionMode.EDIT
        queue_manager = QueueManagerImpl(
            use_multiprocessing=use_multiprocessing
        )
        kernel_manager = KernelManagerImpl(
            queue_manager=queue_manager,
            mode=mode,
            configs=configs,
            app_metadata=app_metadata,
            config_manager=config_manager,
            virtual_files_supported=virtual_files_supported,
            redirect_console_to_browser=redirect_console_to_browser,
        )

        return cls(
            initialization_id=initialization_id,
            session_consumer=session_consumer,
            queue_manager=queue_manager,
            kernel_manager=kernel_manager,
            app_file_manager=app_file_manager,
            config_manager=config_manager,
            ttl_seconds=ttl_seconds,
        )

    def __init__(
        self,
        initialization_id: str,
        session_consumer: SessionConsumer,
        queue_manager: QueueManager,
        kernel_manager: KernelManager,
        app_file_manager: AppFileManager,
        config_manager: MarimoConfigManager,
        ttl_seconds: Optional[int],
    ) -> None:
        """Initialize kernel and client connection to it."""
        # This is some unique ID that we can use to identify the session
        # in edit mode. We don't use the session_id because this can change if
        # the session is resumed
        self.initialization_id = initialization_id
        self.app_file_manager = app_file_manager
        self.room = Room()
        self._queue_manager = queue_manager
        self.kernel_manager = kernel_manager
        self.ttl_seconds = (
            ttl_seconds if ttl_seconds is not None else _DEFAULT_TTL_SECONDS
        )
        self.session_view = SessionView()
        self.session_cache_manager: SessionCacheManager | None = None
        self.config_manager = config_manager
        self.kernel_manager.start_kernel()
        # Reads from the kernel connection and distributes the
        # messages to each subscriber.
        self.message_distributor: (
            ConnectionDistributor[KernelMessage]
            | QueueDistributor[KernelMessage]
        )
        if self.kernel_manager.mode == SessionMode.EDIT:
            self.message_distributor = ConnectionDistributor[KernelMessage](
                self.kernel_manager.kernel_connection
            )
        else:
            q = self._queue_manager.stream_queue
            assert q is not None
            self.message_distributor = QueueDistributor[KernelMessage](queue=q)

        self.message_distributor.add_consumer(
            lambda msg: self.session_view.add_raw_operation(msg)
        )
        self.connect_consumer(session_consumer, main=True)
        self.message_distributor.start()

        self.heartbeat_task: Optional[asyncio.Task[Any]] = None
        self._start_heartbeat()
        self._closed = False

    @property
    def consumers(self) -> Mapping[SessionConsumer, ConsumerId]:
        """Get the consumers in the session."""
        return self.room.consumers

    def _start_heartbeat(self) -> None:
        def _check_alive() -> None:
            if not self.kernel_manager.is_alive():
                LOGGER.debug(
                    "Closing session %s because kernel died",
                    self.initialization_id,
                )
                self.close()
                print_()
                print_tabbed(
                    red(
                        "The Python kernel for file "
                        f"{self.app_file_manager.filename} died unexpectedly."
                    )
                )
                print_()
                self.close()

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

    def put_control_request(
        self,
        request: requests.ControlRequest,
        from_consumer_id: Optional[ConsumerId],
    ) -> None:
        """Put a control request in the control queue."""
        self._queue_manager.control_queue.put(request)
        if isinstance(request, SetUIElementValueRequest):
            self._queue_manager.set_ui_element_queue.put(request)
        # Propagate the control request to the room
        if isinstance(request, (ExecuteMultipleRequest, SyncGraphRequest)):
            if isinstance(request, ExecuteMultipleRequest):
                cell_ids = request.cell_ids
                codes = request.codes
            else:
                cell_ids = request.run_ids
                codes = [request.cells[cell_id] for cell_id in cell_ids]
            self.room.broadcast(
                UpdateCellCodes(
                    cell_ids=cell_ids,
                    codes=codes,
                    # Not stale because we just ran the code
                    code_is_stale=False,
                ),
                except_consumer=from_consumer_id,
            )
            if len(cell_ids) == 1:
                self.room.broadcast(
                    FocusCell(cell_id=cell_ids[0]),
                    except_consumer=from_consumer_id,
                )
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

    def write_operation(
        self,
        operation: MessageOperation,
        from_consumer_id: Optional[ConsumerId],
    ) -> None:
        """Write an operation to the session consumer and the session view."""
        self.session_view.add_operation(operation)
        self.room.broadcast(operation, except_consumer=from_consumer_id)

    def close(self) -> None:
        """
        Close the session.

        This will close the session consumer, kernel, and all kiosk consumers.
        """
        if self._closed:
            return

        self._closed = True
        # Close the room
        self.room.close()
        # Close the kernel
        self.message_distributor.stop()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.session_cache_manager:
            self.session_cache_manager.stop()
        self.kernel_manager.close_kernel()

    def instantiate(
        self,
        request: InstantiateRequest,
        *,
        http_request: Optional[HTTPRequest],
    ) -> None:
        """Instantiate the app."""
        execution_requests = tuple(
            ExecutionRequest(
                cell_id=cell_data.cell_id,
                code=cell_data.code,
                request=http_request,
            )
            for cell_data in self.app_file_manager.app.cell_manager.cell_data()
        )

        self.put_control_request(
            CreationRequest(
                execution_requests=execution_requests,
                set_ui_element_value_request=SetUIElementValueRequest(
                    object_ids=request.object_ids,
                    values=request.values,
                    token=str(uuid4()),
                    request=http_request,
                ),
                auto_run=request.auto_run,
                request=http_request,
            ),
            from_consumer_id=None,
        )

    def sync_session_view_from_cache(self) -> None:
        """Sync the session view from a file.

        Overwrites the existing session view.
        Mutates the existing session.
        """
        from marimo._version import __version__

        LOGGER.debug("Syncing session view from cache")
        self.session_cache_manager = SessionCacheManager(
            session_view=self.session_view,
            path=self.app_file_manager.path,
            interval=self.SESSION_CACHE_INTERVAL_SECONDS,
        )

        app = self.app_file_manager.app
        codes = tuple(
            cell_data.code for cell_data in app.cell_manager.cell_data()
        )
        cell_ids = tuple(app.cell_manager.cell_ids())
        key = SessionCacheKey(
            codes=codes, marimo_version=__version__, cell_ids=cell_ids
        )
        self.session_view = self.session_cache_manager.read_session_view(key)
        self.session_cache_manager.start()

    def __repr__(self) -> str:
        return format_repr(
            self,
            {
                "connection_state": self.connection_state(),
                "room": self.room,
            },
        )
