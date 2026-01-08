# Copyright 2026 Marimo. All rights reserved.
"""Core Session class for managing client sessions.

Each session represents a single client connection with its own Python kernel
and websocket for bidirectional communication.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from marimo import _loggers
from marimo._config.manager import MarimoConfigManager, ScriptConfigManager
from marimo._messaging.notification import (
    NotificationMessage,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._messaging.types import KernelMessage
from marimo._runtime import commands
from marimo._runtime.commands import (
    AppMetadata,
    CreateNotebookCommand,
    ExecuteCellCommand,
    HTTPRequest,
    UpdateUIElementCommand,
)
from marimo._session.consumer import SessionConsumer
from marimo._session.events import SessionEventBus
from marimo._session.extensions.extensions import (
    CachingExtension,
    HeartbeatExtension,
    LoggingExtension,
    NotificationListenerExtension,
    QueueExtension,
    ReplayExtension,
    SessionViewExtension,
)
from marimo._session.extensions.types import SessionExtension
from marimo._session.managers import (
    KernelManagerImpl,
    QueueManagerImpl,
)
from marimo._session.model import ConnectionState, SessionMode
from marimo._session.notebook import AppFileManager
from marimo._session.room import Room
from marimo._session.state.session_view import SessionView
from marimo._session.types import (
    KernelManager,
    KernelState,
    Session,
)
from marimo._types.ids import ConsumerId
from marimo._utils.repr import format_repr

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._server.models.models import InstantiateNotebookRequest

LOGGER = _loggers.marimo_logger()

_DEFAULT_TTL_SECONDS = 120

__all__ = ["Session", "SessionImpl"]


class SessionImpl(Session):
    """A client session.

    Each session has its own Python kernel, for editing and running the app,
    and its own websocket, for sending messages to the client.
    """

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
        auto_instantiate: bool,
        ttl_seconds: Optional[int],
        extensions: list[SessionExtension] | None = None,
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

        extensions = [
            *(extensions or []),
            LoggingExtension(),
            HeartbeatExtension(),
            CachingExtension(
                enabled=not auto_instantiate and mode == SessionMode.EDIT
            ),
            NotificationListenerExtension(
                kernel_manager=kernel_manager, queue_manager=queue_manager
            ),
            QueueExtension(queue_manager=queue_manager),
            ReplayExtension(),
            SessionViewExtension(),
        ]

        return cls(
            initialization_id=initialization_id,
            session_consumer=session_consumer,
            kernel_manager=kernel_manager,
            app_file_manager=app_file_manager,
            config_manager=config_manager,
            ttl_seconds=ttl_seconds,
            extensions=extensions,
        )

    def __init__(
        self,
        initialization_id: str,
        session_consumer: SessionConsumer,
        kernel_manager: KernelManager,
        app_file_manager: AppFileManager,
        config_manager: MarimoConfigManager,
        ttl_seconds: Optional[int],
        extensions: list[SessionExtension],
    ) -> None:
        """Initialize kernel and client connection to it."""
        # This is some unique ID that we can use to identify the session
        # in edit mode. We don't use the session_id because this can change if
        # the session is resumed
        self.initialization_id = initialization_id
        self.app_file_manager = app_file_manager
        self.room = Room()
        self._kernel_manager = kernel_manager
        self.ttl_seconds = (
            ttl_seconds if ttl_seconds is not None else _DEFAULT_TTL_SECONDS
        )
        self.session_view = SessionView()
        self.config_manager = config_manager
        self.extensions = extensions

        self._kernel_manager.start_kernel()
        self._event_bus = SessionEventBus()

        self._closed = False

        # Attach all extensions
        self._attach_extensions()
        # Connect the main consumer after attaching extensions,
        # to avoid calling on_attach on the main consumer twice.
        self.connect_consumer(session_consumer, main=True)

    def _attach_extensions(self) -> None:
        """Attach all extensions to the session."""
        for extension in self.extensions:
            try:
                extension.on_attach(self, self._event_bus)
            except Exception as e:
                LOGGER.error(
                    "Error attaching extension %s: %s",
                    extension,
                    e,
                )
                continue

    def _detach_extensions(self) -> None:
        """Detach all extensions from the session."""
        for extension in self.extensions:
            try:
                extension.on_detach()
            except Exception as e:
                LOGGER.error(
                    "Error detaching extension %s: %s",
                    extension,
                    e,
                )
                continue

    @property
    def consumers(self) -> Mapping[SessionConsumer, ConsumerId]:
        """Get the consumers in the session."""
        return self.room.consumers

    def flush_messages(self) -> None:
        """Flush any pending messages."""
        # HACK: Ideally we don't need to reach into this extension directly
        for extension in self.extensions:
            if isinstance(extension, NotificationListenerExtension):
                if extension.distributor is not None:
                    extension.distributor.flush()
                return

    async def rename_path(self, new_path: str) -> None:
        """Rename the path of the session."""
        old_path = self.app_file_manager.path
        self.app_file_manager.rename(new_path)
        await self._event_bus.emit_session_notebook_renamed(self, old_path)

    def try_interrupt(self) -> None:
        """Try to interrupt the kernel."""
        self._kernel_manager.interrupt_kernel()

    def kernel_state(self) -> KernelState:
        """Get the state of the kernel."""
        if self._kernel_manager.kernel_task is None:
            return KernelState.NOT_STARTED
        if self._kernel_manager.kernel_task.is_alive():
            return KernelState.RUNNING
        return KernelState.STOPPED

    def kernel_pid(self) -> int | None:
        """Get the PID of the kernel."""
        return self._kernel_manager.pid

    def put_control_request(
        self,
        request: commands.CommandMessage,
        from_consumer_id: Optional[ConsumerId],
    ) -> None:
        """Put a control request in the control queue."""
        self._event_bus.emit_received_command(self, request, from_consumer_id)

    def put_input(self, text: str) -> None:
        """Put an input() request in the input queue."""
        self._event_bus.emit_received_stdin(self, text)

    def disconnect_consumer(self, session_consumer: SessionConsumer) -> None:
        """
        Stop the session consumer but keep the kernel running.

        This will disconnect the main session consumer,
        or a kiosk consumer.
        """
        self.room.remove_consumer(session_consumer)
        self.extensions.remove(session_consumer)

    def disconnect_main_consumer(self) -> None:
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
        # Consumers are also extensions, so we want to attach them to the session
        self.extensions.append(session_consumer)
        session_consumer.on_attach(self, self._event_bus)
        self.room.add_consumer(
            session_consumer,
            consumer_id=session_consumer.consumer_id,
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

    def notify(
        self,
        operation: NotificationMessage | KernelMessage,
        from_consumer_id: Optional[ConsumerId],
    ) -> None:
        """Write an operation to the session consumer and the session view."""
        if isinstance(operation, bytes):
            notification = operation
        else:
            notification = serialize_kernel_message(operation)
        self.room.broadcast(notification, except_consumer=from_consumer_id)
        self._event_bus.emit_notification_sent(self, notification)

    def close(self) -> None:
        """
        Close the session.

        This will close the session consumer, kernel, and all kiosk consumers.
        """
        if self._closed:
            return

        self._closed = True

        # Close extensions
        self._detach_extensions()
        # Close the room
        self.room.close()
        self._kernel_manager.close_kernel()

    def instantiate(
        self,
        request: InstantiateNotebookRequest,
        *,
        http_request: Optional[HTTPRequest],
    ) -> None:
        """Instantiate the app."""

        # If codes are provided, use them instead of the file codes
        # This is used when the frontend has local edits that should be
        # used instead of the stored file (e.g. local editing before connecting).
        codes = (
            request.codes or self.app_file_manager.app.cell_manager.code_map()
        )

        execution_requests = tuple(
            ExecuteCellCommand(
                cell_id=cell_id,
                code=code,
                request=http_request,
            )
            for cell_id, code in codes.items()
        )

        self.put_control_request(
            CreateNotebookCommand(
                execution_requests=execution_requests,
                set_ui_element_value_request=UpdateUIElementCommand(
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

    def __repr__(self) -> str:
        return format_repr(
            self,
            {
                "connection_state": self.connection_state(),
                "room": self.room,
            },
        )
