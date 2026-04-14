# Copyright 2026 Marimo. All rights reserved.
"""Session extensions for composable session features.

Extensions provide a way to add cross-cutting concerns to sessions
(like heartbeat monitoring, caching, metrics) without modifying SessionImpl.
"""

from __future__ import annotations

import asyncio
import html
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import TYPE_CHECKING

import msgspec

from marimo import _loggers
from marimo._cli.print import red
from marimo._messaging.notebook.document import NotebookCell
from marimo._messaging.notification import (
    AlertNotification,
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
        # Debug-log the "unnamed notebook, skipping auto-save" warning once
        # per session instead of on every code_mode mutation.
        self._unnamed_autosave_logged = False
        # Dedicated single-worker executor for auto-save. Using
        # ``max_workers=1`` guarantees FIFO ordering of dispatched saves
        # so a slower older snapshot never overwrites a newer one.
        # Started lazily — run mode and unnamed notebooks never need it.
        # TODO: if other extensions need the same "dispatch blocking
        # I/O to a dedicated per-session worker" pattern, extract into
        # ``marimo/_utils`` as a ``SerialTaskRunner`` or similar.
        self._autosave_executor: ThreadPoolExecutor | None = None
        # Futures for in-flight auto-saves. Populated only in the
        # ``ConnectionDistributor`` path (edit mode, same process as
        # the server event loop). Tests await these to synchronize
        # with fire-and-forget dispatch.
        self._pending_autosaves: list[asyncio.Future[None]] = []

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
        kernel_transaction_applied = False

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
                kernel_transaction_applied = applied.source == "kernel"
            except Exception:
                LOGGER.warning(
                    "Failed to decode/apply kernel document transaction"
                )

        session.notify(notif, from_consumer_id=None)

        if kernel_transaction_applied:
            self._maybe_autosave(session)

    def _maybe_autosave(self, session: Session) -> None:
        """Persist the kernel-driven mutation to disk best-effort.

        Skipped in run mode and for unnamed notebooks. Failures are logged
        and surfaced to the frontend via an ``AlertNotification`` so the
        user sees a toast; they never raise out of the interceptor.

        The file I/O is offloaded to ``run_in_executor`` when called from
        the asyncio event loop (``ConnectionDistributor`` in edit mode),
        so the loop is never stalled by disk writes. When called from the
        ``QueueDistributor`` worker thread (IPC kernels, run mode), the
        save runs inline on that worker thread.
        """
        if self.kernel_manager.mode != SessionMode.EDIT:
            return

        if session.app_file_manager.path is None:
            if not self._unnamed_autosave_logged:
                LOGGER.debug(
                    "Skipping code_mode auto-save for unnamed notebook"
                )
                self._unnamed_autosave_logged = True
            return

        # Snapshot cells on the caller thread: ``NotebookDocument`` is not
        # thread-safe for concurrent reads/writes, and only this thread
        # (the one that called ``document.apply()`` above) knows the
        # document is quiescent right now. The executor only touches the
        # frozen list.
        cells_snapshot: list[NotebookCell] = list(session.document.cells)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            self._do_autosave(session, cells_snapshot, loop=None)
        else:
            if self._autosave_executor is None:
                self._autosave_executor = ThreadPoolExecutor(
                    max_workers=1,
                    thread_name_prefix="marimo-autosave",
                )
            fut = loop.run_in_executor(
                self._autosave_executor,
                self._do_autosave,
                session,
                cells_snapshot,
                loop,
            )
            # Prune already-done futures on each enqueue so the list
            # doesn't grow unboundedly across thousands of mutations.
            self._pending_autosaves = [
                f for f in self._pending_autosaves if not f.done()
            ]
            self._pending_autosaves.append(fut)

    def _do_autosave(
        self,
        session: Session,
        cells: list[NotebookCell],
        loop: asyncio.AbstractEventLoop | None,
    ) -> None:
        """Write the snapshot to disk; on failure, post an alert toast.

        Runs on the event loop thread when ``loop is None`` and on an
        executor thread otherwise. The alert broadcast is scheduled back
        to the loop via ``call_soon_threadsafe`` when we're off-loop,
        because ``session.notify`` ultimately writes to an ``asyncio.Queue``
        which is not thread-safe.
        """
        try:
            session.app_file_manager.save_from_cells(cells)
            return
        except Exception as err:
            save_error: Exception = err

        LOGGER.warning(
            "Failed to auto-save notebook after kernel mutation: %s",
            save_error,
        )

        path = session.app_file_manager.path
        alert = AlertNotification(
            title="Auto-save failed",
            description=html.escape(
                f"Could not persist kernel changes to {path}: {save_error}"
            ),
            variant="danger",
        )

        def _broadcast() -> None:
            try:
                session.notify(alert, from_consumer_id=None)
            except Exception:
                LOGGER.exception("Failed to broadcast auto-save failure alert")

        if loop is not None:
            loop.call_soon_threadsafe(_broadcast)
        else:
            _broadcast()

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
        if self._autosave_executor is not None:
            # Don't wait: the session is going away and we don't want to
            # block the event loop on a slow disk write. Pending saves
            # are best-effort and the notebook state is still in the
            # kernel if the user reopens.
            self._autosave_executor.shutdown(wait=False)
            self._autosave_executor = None

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
