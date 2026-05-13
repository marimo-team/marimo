# Copyright 2026 Marimo. All rights reserved.
"""Session extensions for composable session features.

Extensions provide a way to add cross-cutting concerns to sessions
(like heartbeat monitoring, caching, metrics) without modifying SessionImpl.
"""

from __future__ import annotations

import asyncio
import copy
import html
from enum import Enum
from functools import partial
from typing import TYPE_CHECKING

import msgspec

from marimo import _loggers
from marimo._cli.print import red
from marimo._messaging.notebook.changes import TransactionSource
from marimo._messaging.notebook.document import NotebookCell
from marimo._messaging.notification import (
    AlertNotification,
    BannerNotification,
    NotebookDocumentTransactionNotification,
    NotificationMessage,
)
from marimo._messaging.serde import try_deserialize_kernel_notification_name
from marimo._messaging.types import KernelMessage
from marimo._runtime import commands
from marimo._session.extensions.types import (
    EventAwareExtension,
    SessionExtension,
)
from marimo._session.model import SessionMode
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
from marimo._utils.serial_task_runner import SerialTaskRunner

if TYPE_CHECKING:
    from logging import Logger

    from marimo._session.events import (
        SessionEventBus,
    )
    from marimo._session.types import Session
    from marimo._types.ids import ConsumerId, SessionId

LOGGER = _loggers.marimo_logger()


class CacheMode(Enum):
    READ = "read"
    READ_WRITE = "write"


class HeartbeatExtension(SessionExtension):
    """Extension for monitoring kernel health and handling kernel death.

    Periodically checks if the kernel is alive and triggers cleanup
    when the kernel dies unexpectedly.
    """

    def __init__(self) -> None:
        self.heartbeat_task: asyncio.Task[None] | None = None

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        del event_bus
        self._start(session)

    def on_detach(self) -> None:
        self._stop()

    def _start(self, session: Session) -> None:
        """Start the heartbeat monitoring."""

        async def _check_alive() -> None:
            # Outer guard: an unhandled exception here would kill the
            # heartbeat task and we'd never detect future kernel deaths in
            # this session's lifetime. CancelledError is re-raised so detach
            # still cleanly stops the task.
            try:
                if session.kernel_state() != KernelState.STOPPED:
                    return
                exit_info = session.kernel_exit_info()
                LOGGER.debug("Kernel died, invoking cleanup callback")
                reason = (
                    exit_info.message if exit_info is not None else "unknown"
                )
                # Notify the frontend before closing the WS so the user sees
                # a persistent banner with the real cause instead of just a
                # "disconnected" UI. ``notify`` only queues the frame on each
                # consumer's send queue; yield to the event loop afterwards
                # so the WS writer task drains it before ``session.close``
                # detaches the consumers. Inner guard isolates a broadcast
                # failure from cleanup -- we still want to close the session
                # and log even if the banner can't be delivered.
                try:
                    session.notify(
                        BannerNotification(
                            title="Kernel stopped",
                            description=html.escape(reason),
                            variant="danger",
                            action="restart",
                        ),
                        from_consumer_id=None,
                    )
                    await asyncio.sleep(0.1)
                except Exception:
                    LOGGER.exception("Failed to broadcast kernel-died banner")
                session.close()
                print_()
                filename = session.app_file_manager.filename
                filename_str = filename or "unknown"
                print_tabbed(
                    red(
                        f"The Python kernel for file {filename_str} died: "
                        f"{reason}"
                    )
                )
                print_()
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Unexpected error in kernel heartbeat check")

        async def _heartbeat() -> None:
            while True:
                await asyncio.sleep(1)
                await _check_alive()

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


class CachingExtension(EventAwareExtension):
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
        mode: CacheMode = CacheMode.READ_WRITE,
    ) -> None:
        """Initialize the caching extension.

        Args:
            enabled: Whether to enable caching
            interval: How often to write cache (in seconds)
            mode: Whether to read cache only or read/write.
        """
        super().__init__()
        self.interval = interval
        self.enabled = enabled
        self.mode = mode
        self.session_cache_manager: SessionCacheManager | None = None

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        """Initialize cache manager when attached to session."""
        if not self.enabled:
            return

        super().on_attach(session, event_bus)

        from marimo._utils.inline_script_metadata import (
            script_metadata_hash_from_filename,
        )
        from marimo._version import __version__

        LOGGER.debug("Syncing session view from cache")
        self.session_cache_manager = SessionCacheManager(
            session_view=session.session_view,
            document=session.document,
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
            codes=codes,
            marimo_version=__version__,
            cell_ids=cell_ids,
            script_metadata_hash=script_metadata_hash_from_filename(
                session.app_file_manager.path
            )
            if session.app_file_manager.path is not None
            else None,
        )
        session.session_view = self.session_cache_manager.read_session_view(
            key
        )

        # Start the background task to write the session view to disk
        if self.mode is CacheMode.READ_WRITE:
            self.session_cache_manager.start()

    def on_detach(self) -> None:
        """Stop cache manager when detached."""
        self._stop()
        super().on_detach()

    async def on_session_notebook_renamed(
        self, session: Session, old_path: str | None
    ) -> None:
        """Rename the path for the cache manager."""
        del old_path
        if self.mode is not CacheMode.READ_WRITE:
            return
        path = session.app_file_manager.path
        if self.session_cache_manager and path:
            self.session_cache_manager.rename_path(path)
        return

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
        self.distributor: Distributor[KernelMessage] | None = None
        # Log the unnamed-notebook skip once per session, not per mutation.
        self._unnamed_autosave_logged = False
        # FIFO so a slow older save never clobbers a newer one.
        self._autosave_runner = SerialTaskRunner(
            thread_name_prefix="marimo-autosave"
        )

    def _create_distributor(
        self,
        kernel_manager: KernelManager,
        queue_manager: QueueManager,
    ) -> Distributor[KernelMessage]:
        # IPC kernels (home sandbox mode) and run mode use stream_queue
        # Edit mode without IPC uses kernel_connection
        if queue_manager.stream_queue is not None:
            return QueueDistributor(queue=queue_manager.stream_queue)
        else:
            # Edit mode with original kernel manager uses connection
            return ConnectionDistributor(kernel_manager.kernel_connection)

    def _on_kernel_message(self, session: Session, msg: KernelMessage) -> None:
        """Route a raw kernel message to the appropriate session method.

        Document transactions are intercepted and applied to the
        ``session.document``, then ``session.notify()`` is invoked with the (versioned) result.

        Kernel-sourced transactions also trigger an auto-save so agent-driven
        mutations via ``code_mode`` land on disk the same way frontend edits do.

        Everything else is forwarded verbatim via ``session.notify()``.

        TODO: if more notification types need server-side interception,
        consider a middleware chain instead of inline dispatch.
        """
        notif: KernelMessage | NotificationMessage = msg
        applied_source: TransactionSource | None = None

        name = try_deserialize_kernel_notification_name(msg)
        if name == NotebookDocumentTransactionNotification.name:
            try:
                decoded = msgspec.json.decode(
                    msg,
                    type=NotebookDocumentTransactionNotification,
                )
                applied = session.document.apply(decoded.transaction)
                notif = NotebookDocumentTransactionNotification(
                    transaction=applied
                )
                applied_source = applied.source
            except Exception:
                LOGGER.warning(
                    "Failed to decode/apply kernel document transaction"
                )

        session.notify(notif, from_consumer_id=None)

        if applied_source is not None:
            self._maybe_autosave(session, applied_source)

    def _maybe_autosave(
        self, session: Session, source: TransactionSource
    ) -> None:
        """Best-effort persistence of code-mode mutations to disk.

        Only ``source="code-mode"`` transactions persist; ``"kernel"``
        bookkeeping (e.g. instantiation cell-order broadcasts) is skipped
        so opening or running a notebook never rewrites it on disk.
        Skipped in run mode and for unnamed notebooks. Failures surface as
        an ``AlertNotification`` toast; they never raise out of the
        interceptor.
        """
        if source != "code-mode":
            return
        if self.kernel_manager.mode != SessionMode.EDIT:
            return

        expected_filename, expected_generation = (
            session.app_file_manager.capture_autosave_target()
        )
        if expected_filename is None:
            if not self._unnamed_autosave_logged:
                LOGGER.debug(
                    "Skipping code_mode auto-save for unnamed notebook"
                )
                self._unnamed_autosave_logged = True
            return

        # Deep-copy on the caller thread. ``NotebookCell`` and
        # ``CellConfig`` are mutable and owned by the document, so a
        # shallow copy would let the event-loop thread mutate fields
        # under the worker thread's feet (torn snapshot).
        cells_snapshot: list[NotebookCell] = copy.deepcopy(
            session.document.cells
        )

        self._autosave_runner.submit(
            partial(
                session.app_file_manager.save_from_cells,
                cells_snapshot,
                expected_filename=expected_filename,
                expected_generation=expected_generation,
            ),
            on_error=partial(self._post_autosave_failure, session),
        )

    @staticmethod
    def _post_autosave_failure(session: Session, err: Exception) -> None:
        # Runs on the event loop thread — the runner routes on_error there
        # so session.notify can safely touch the per-consumer asyncio.Queue.
        LOGGER.warning(
            "Failed to auto-save notebook after kernel mutation: %s", err
        )
        try:
            session.notify(
                AlertNotification(
                    title="Auto-save failed",
                    description=html.escape(
                        f"Could not persist kernel changes to "
                        f"{session.app_file_manager.path}: {err}"
                    ),
                    variant="danger",
                ),
                from_consumer_id=None,
            )
        except Exception:
            LOGGER.exception("Failed to broadcast auto-save failure alert")

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        del event_bus
        self.distributor = self._create_distributor(
            kernel_manager=self.kernel_manager,
            queue_manager=self.queue_manager,
        )
        self.distributor.add_consumer(
            lambda msg: self._on_kernel_message(session, msg)
        )
        self.distributor.start()

    def on_detach(self) -> None:
        if self.distributor is not None:
            self.distributor.stop()
            self.distributor = None
        # Don't block session close on disk I/O; kernel still holds state.
        self._autosave_runner.shutdown(wait=False)

    def flush(self) -> None:
        """Flush any pending messages from the distributor."""
        if self.distributor is not None:
            self.distributor.flush()


class LoggingExtension(EventAwareExtension):
    """Extension for logging session events."""

    def __init__(self, logger: Logger = LOGGER) -> None:
        super().__init__()
        self.logger = logger

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        self.logger.debug("Attaching extensions")
        super().on_attach(session, event_bus)

    def on_detach(self) -> None:
        self.logger.debug("Detaching extensions")
        super().on_detach()

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


class SessionViewExtension(EventAwareExtension):
    """Extension for listening to session view updates."""

    def on_received_command(
        self,
        session: Session,
        request: commands.CommandMessage,
        from_consumer_id: ConsumerId | None,
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


class QueueExtension(EventAwareExtension):
    """Extension for handling queue operations."""

    def __init__(self, queue_manager: QueueManager) -> None:
        super().__init__()
        self.queue_manager = queue_manager

    def on_received_command(
        self,
        session: Session,
        request: commands.CommandMessage,
        from_consumer_id: ConsumerId | None,
    ) -> None:
        """Called when a command is received."""
        del session
        del from_consumer_id
        self.queue_manager.put_control_request(request)

    def on_received_stdin(self, session: Session, stdin: str) -> None:
        """Called when stdin is received."""
        del session
        self.queue_manager.put_input(stdin)


class ReplayExtension(EventAwareExtension):
    """Extension for replaying commands from one session to another."""

    def on_received_command(
        self,
        session: Session,
        request: commands.CommandMessage,
        from_consumer_id: ConsumerId | None,
    ) -> None:
        """Called when a command is received."""
        from marimo._messaging.notification import (
            FocusCellNotification,
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
        else:
            cell_ids = request.run_ids

        # Send focus cell notification
        if len(cell_ids) == 1:
            session.notify(
                FocusCellNotification(cell_id=cell_ids[0]),
                from_consumer_id=from_consumer_id,
            )
