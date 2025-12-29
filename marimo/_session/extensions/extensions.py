# Copyright 2026 Marimo. All rights reserved.
"""Session extensions for composable session features.

Extensions provide a way to add cross-cutting concerns to sessions
(like heartbeat monitoring, caching, metrics) without modifying SessionImpl.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

from marimo import _loggers
from marimo._cli.print import red
from marimo._messaging.types import KernelMessage
from marimo._runtime import commands
from marimo._session.events import SessionEventListener
from marimo._session.extensions.types import SessionExtension
from marimo._session.state.serialize import (
    SessionCacheKey,
    SessionCacheManager,
)
from marimo._session.types import (
    KernelManager,
    KernelState,
    QueueManager,
)
from marimo._utils.distributor import (
    ConnectionDistributor,
    Distributor,
    QueueDistributor,
)
from marimo._utils.print import print_, print_tabbed

if TYPE_CHECKING:
    from logging import Logger

    from marimo._session.events import (
        SessionEventBus,
    )
    from marimo._session.types import Session
    from marimo._types.ids import ConsumerId, SessionId

LOGGER = _loggers.marimo_logger()


class HeartbeatExtension(SessionExtension):
    """Extension for monitoring kernel health and handling kernel death.

    Periodically checks if the kernel is alive and triggers cleanup
    when the kernel dies unexpectedly.
    """

    def __init__(self) -> None:
        self.heartbeat_task: Optional[asyncio.Task[None]] = None

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        del event_bus
        self._start(session)

    def on_detach(self) -> None:
        self._stop()

    def _start(self, session: Session) -> None:
        """Start the heartbeat monitoring."""

        def _check_alive() -> None:
            if session.kernel_state() == KernelState.STOPPED:
                LOGGER.debug("Kernel died, invoking cleanup callback")
                session.close()
                print_()
                filename = session.app_file_manager.filename
                filename_str = filename or "unknown"
                print_tabbed(
                    red(
                        "The Python kernel for file "
                        f"{filename_str} died unexpectedly."
                    )
                )
                print_()

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

    def _stop(self) -> None:
        """Stop the heartbeat monitoring."""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()


class CachingExtension(SessionExtension, SessionEventListener):
    """Extension for caching session state to disk.

    Periodically writes session state to disk so it can be restored
    on reconnection or browser refresh.
    """

    SESSION_CACHE_INTERVAL_SECONDS = 2

    def __init__(
        self,
        *,
        enabled: bool,
        interval: int = SESSION_CACHE_INTERVAL_SECONDS,
    ) -> None:
        """Initialize the caching extension.

        Args:
            enabled: Whether to enable caching
            interval: How often to write cache (in seconds)
        """
        self.interval = interval
        self.enabled = enabled
        self.session_cache_manager: Optional[SessionCacheManager] = None
        self.event_bus: Optional[SessionEventBus] = None

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        """Initialize cache manager when attached to session."""
        if not self.enabled:
            return

        # Subscribe to events (like rename)
        event_bus.subscribe(self)
        self.event_bus = event_bus

        from marimo._version import __version__

        LOGGER.debug("Syncing session view from cache")
        self.session_cache_manager = SessionCacheManager(
            session_view=session.session_view,
            path=session.app_file_manager.path,
            interval=self.interval,
        )

        # Serialize the session view based on the current app
        app = session.app_file_manager.app
        codes = tuple(
            cell_data.code for cell_data in app.cell_manager.cell_data()
        )
        cell_ids = tuple(app.cell_manager.cell_ids())
        key = SessionCacheKey(
            codes=codes, marimo_version=__version__, cell_ids=cell_ids
        )
        session.session_view = self.session_cache_manager.read_session_view(
            key
        )

        # Start the background task to write the session view to disk
        self.session_cache_manager.start()

    def on_detach(self) -> None:
        """Stop cache manager when detached."""
        self._stop()
        if self.event_bus:
            self.event_bus.unsubscribe(self)
            self.event_bus = None

    async def on_session_notebook_renamed(
        self, session: Session, old_path: str | None
    ) -> None:
        """Rename the path for the cache manager."""
        del old_path
        path = session.app_file_manager.path
        if self.session_cache_manager and path:
            self.session_cache_manager.rename_path(path)
        return None

    def _stop(self) -> None:
        """Stop the cache manager."""
        if self.session_cache_manager:
            self.session_cache_manager.stop()
            self.session_cache_manager = None


class NotificationListenerExtension(SessionExtension):
    """Extension for listening to notifications from the kernel and forwarding them to the session."""

    def __init__(
        self, kernel_manager: KernelManager, queue_manager: QueueManager
    ) -> None:
        self.kernel_manager = kernel_manager
        self.queue_manager = queue_manager
        self.distributor: Optional[Distributor[KernelMessage]] = None

    def _create_distributor(
        self,
        kernel_manager: KernelManager,
        queue_manager: QueueManager,
    ) -> Distributor[KernelMessage]:
        from marimo._session.model import SessionMode

        if kernel_manager.mode == SessionMode.EDIT:
            return ConnectionDistributor(kernel_manager.kernel_connection)
        else:
            q = queue_manager.stream_queue
            assert q is not None
            return QueueDistributor(queue=q)

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        del event_bus
        self.distributor = self._create_distributor(
            kernel_manager=self.kernel_manager,
            queue_manager=self.queue_manager,
        )
        self.distributor.add_consumer(
            lambda msg: session.notify(msg, from_consumer_id=None)
        )
        self.distributor.start()

    def on_detach(self) -> None:
        if self.distributor is not None:
            self.distributor.stop()
            self.distributor = None


class LoggingExtension(SessionExtension, SessionEventListener):
    """Extension for logging session events."""

    def __init__(self, logger: Logger = LOGGER) -> None:
        self.logger = logger
        self.event_bus: Optional[SessionEventBus] = None

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        del session
        self.logger.debug("Attaching extensions")
        event_bus.subscribe(self)
        self.event_bus = event_bus

    def on_detach(self) -> None:
        self.logger.debug("Detaching extensions")
        if self.event_bus:
            self.event_bus.unsubscribe(self)
            self.event_bus = None

    async def on_session_created(self, session: Session) -> None:
        self.logger.debug("Session created: %s", session.initialization_id)

    async def on_session_closed(self, session: Session) -> None:
        self.logger.debug("Session closed: %s", session.initialization_id)

    async def on_session_resumed(
        self, session: Session, old_id: SessionId
    ) -> None:
        self.logger.debug(
            "Session resumed: %s (old id: %s)",
            session.initialization_id,
            old_id,
        )

    async def on_session_notebook_renamed(
        self, session: Session, old_path: str | None
    ) -> None:
        self.logger.debug(
            "Session file renamed: %s (new path: %s)",
            session.initialization_id,
            old_path,
        )


class SessionViewExtension(SessionExtension, SessionEventListener):
    """Extension for listening to session view updates."""

    def __init__(self) -> None:
        self.event_bus: Optional[SessionEventBus] = None

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        """Attach the session view extension to a session."""
        del session
        self.event_bus = event_bus
        self.event_bus.subscribe(self)

    def on_detach(self) -> None:
        """Detach the session view extension from a session."""
        if self.event_bus:
            self.event_bus.unsubscribe(self)
            self.event_bus = None

    def on_received_command(
        self,
        session: Session,
        request: commands.CommandMessage,
        from_consumer_id: Optional[ConsumerId],
    ) -> None:
        """Called when a command is received."""
        del from_consumer_id
        # Only add control requests to session view, not completion requests
        if not isinstance(request, commands.CodeCompletionCommand):
            session.session_view.add_control_request(request)

    def on_received_stdin(self, session: Session, stdin: str) -> None:
        """Called when stdin is received."""
        session.session_view.add_stdin(stdin)

    def on_notification_sent(
        self, session: Session, notification: KernelMessage
    ) -> None:
        """Called when a notification is sent."""
        session.session_view.add_raw_notification(notification)


class QueueExtension(SessionExtension, SessionEventListener):
    """Extension for handling queue operations."""

    def __init__(self, queue_manager: QueueManager) -> None:
        self.queue_manager = queue_manager
        self.event_bus: Optional[SessionEventBus] = None

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        """Attach the queue extension to a session."""
        del session
        self.event_bus = event_bus
        self.event_bus.subscribe(self)

    def on_detach(self) -> None:
        """Detach the queue extension from a session."""
        if self.event_bus:
            self.event_bus.unsubscribe(self)
            self.event_bus = None

    def on_received_command(
        self,
        session: Session,
        request: commands.CommandMessage,
        from_consumer_id: Optional[ConsumerId],
    ) -> None:
        """Called when a command is received."""
        del session
        del from_consumer_id
        self.queue_manager.put_control_request(request)

    def on_received_stdin(self, session: Session, stdin: str) -> None:
        """Called when stdin is received."""
        del session
        self.queue_manager.put_input(stdin)


class ReplayExtension(SessionExtension, SessionEventListener):
    """Extension for replaying commands from one session to another."""

    def __init__(self) -> None:
        self.event_bus: Optional[SessionEventBus] = None

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        """Attach the replay extension to a session."""
        del session
        self.event_bus = event_bus
        self.event_bus.subscribe(self)

    def on_detach(self) -> None:
        """Detach the replay extension from a session."""
        if self.event_bus:
            self.event_bus.unsubscribe(self)
            self.event_bus = None

    def on_received_command(
        self,
        session: Session,
        request: commands.CommandMessage,
        from_consumer_id: Optional[ConsumerId],
    ) -> None:
        """Called when a command is received."""
        from marimo._messaging.notification import (
            FocusCellNotification,
            UpdateCellCodesNotification,
        )
        from marimo._runtime.commands import (
            ExecuteCellsCommand,
            SyncGraphCommand,
        )

        # Only propagate execute cells and sync graph commands to the room
        if not isinstance(request, (ExecuteCellsCommand, SyncGraphCommand)):
            return

        # Collect cell ids and codes
        if isinstance(request, ExecuteCellsCommand):
            cell_ids = request.cell_ids
            codes = request.codes
        else:
            cell_ids = request.run_ids
            codes = [request.cells[cell_id] for cell_id in cell_ids]

        # Send update cell codes notification
        if cell_ids:
            session.notify(
                UpdateCellCodesNotification(
                    cell_ids=cell_ids,
                    codes=codes,
                    # Not stale because we just ran the code
                    code_is_stale=False,
                ),
                from_consumer_id=from_consumer_id,
            )

        # Send focus cell notification
        if len(cell_ids) == 1:
            session.notify(
                FocusCellNotification(cell_id=cell_ids[0]),
                from_consumer_id=from_consumer_id,
            )
