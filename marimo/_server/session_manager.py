# Copyright 2026 Marimo. All rights reserved.
"""Session manager for coordinating multiple sessions.

The SessionManager maintains a mapping from client session IDs to sessions
and encapsulates state common to all sessions including auth tokens,
file watching, and LSP server management.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING
from uuid import uuid4
from weakref import WeakValueDictionary

from marimo import _loggers
from marimo._config.manager import MarimoConfigManager
from marimo._messaging.notification import StartupProgressNotification
from marimo._messaging.serde import serialize_kernel_message
from marimo._runtime.commands import (
    SerializedCLIArgs,
    SerializedQueryParams,
)
from marimo._server.app_defaults import AppDefaults
from marimo._server.lsp import LspServer
from marimo._server.recents import RecentFilesManager
from marimo._server.resume_strategies import create_resume_strategy
from marimo._server.session.listeners import RecentsTrackerListener
from marimo._server.token_manager import TokenManager
from marimo._server.tokens import AuthToken, SkewProtectionToken
from marimo._server.workspace import (
    NEW_FILE,
    MarimoFileKey,
    NotebookWorkspace,
    flatten_files,
)
from marimo._session.app_host import AppHostContext, AppHostPool
from marimo._session.consumer import SessionConsumer
from marimo._session.events import SessionEventBus
from marimo._session.extensions.types import (
    EventAwareExtension,
    SessionExtension,
)
from marimo._session.file_change_handler import (
    FileChangeCoordinator,
    create_reload_strategy,
)
from marimo._session.file_watcher_integration import (
    SessionFileWatcherExtension,
)
from marimo._session.managers.ipc import KernelStartupError
from marimo._session.model import ConnectionState, SessionMode, StartupPhase
from marimo._session.requests import InstantiateNotebookRequest
from marimo._session.session import (
    Session,
    SessionImpl,
    new_stable_session_id,
)
from marimo._session.session_repository import SessionRepository
from marimo._session.types import KernelExitInfo, KernelState, SessionSnapshot
from marimo._types.ids import ConsumerId, SessionId
from marimo._utils.asyncio_utils import fire_and_forget
from marimo._utils.file_watcher import FileWatcherManager
from marimo._utils.http import HTTPException

if TYPE_CHECKING:
    from collections.abc import (
        AsyncGenerator,
        AsyncIterator,
        Callable,
        Mapping,
    )

    from marimo._session.notebook import AppFileManager

LOGGER = _loggers.marimo_logger()
_TERMINAL_RETENTION_SECONDS = 300


@dataclass
class _PendingSession:
    task: asyncio.Task[Session]
    snapshot: SessionSnapshot
    server_owned: bool = False
    waiters: int = 0


class _SessionStateListener(EventAwareExtension):
    def __init__(self, manager: SessionManager) -> None:
        super().__init__()
        self._manager = manager

    async def on_session_notebook_renamed(
        self, session: Session, old_path: str | None
    ) -> None:
        del old_path
        self._manager._notify_session_changed(session.stable_id)

    def on_detach(self) -> None:
        snapshot = SessionSnapshot.from_session(self.session)
        self._manager._retain_session(
            replace(
                snapshot,
                status="failed"
                if snapshot.status == "failed"
                else "terminated",
            )
        )
        super().on_detach()


class SessionManager:
    """Orchestrates session management

    - SessionRepository: stores sessions
    - TokenManager: manages auth tokens
    - SessionEventBus: coordinates lifecycle events
    - ResumeStrategy: handles session resumption logic
    - FileWatcherLifecycle: manages file watching
    """

    def __init__(
        self,
        *,
        workspace: NotebookWorkspace,
        mode: SessionMode,
        quiet: bool,
        include_code: bool,
        lsp_server: LspServer,
        config_manager: MarimoConfigManager,
        cli_args: SerializedCLIArgs,
        argv: list[str] | None,
        auth_token: AuthToken | None,
        redirect_console_to_browser: bool,
        ttl_seconds: int | None,
        watch: bool = False,
        sandbox: bool = False,
        isolate_apps: bool = False,
        execute_opengraph_generators: bool = False,
    ) -> None:
        # Core configuration
        self.workspace = workspace
        self.mode = mode
        self.quiet = quiet
        self.include_code = include_code
        self.ttl_seconds = ttl_seconds
        self.lsp_server = lsp_server
        self.cli_args = cli_args
        self.argv = argv
        self.redirect_console_to_browser = redirect_console_to_browser
        self._config_manager = config_manager
        self.sandbox = sandbox
        self.execute_opengraph_generators = execute_opengraph_generators

        # When running multiple apps, each app runs in an isolated  host
        # process, to avoid collisions in sys.modules and other Python global
        # structures. These processes are managed by an AppHostPool.
        self._app_host_pool: AppHostPool | None = None
        if isolate_apps and mode == SessionMode.RUN:
            self._app_host_pool = AppHostPool(
                sandbox=sandbox,
            )

        self._repository = SessionRepository()
        self._pending: dict[SessionId, _PendingSession] = {}
        self._terminal_sessions: dict[str, tuple[float, SessionSnapshot]] = {}
        self._session_subscribers: dict[
            str, set[asyncio.Queue[SessionSnapshot]]
        ] = {}
        self._connection_locks: WeakValueDictionary[str, asyncio.Lock] = (
            WeakValueDictionary()
        )
        self._closed = False

        def _get_code() -> str:
            defaults = AppDefaults.from_config_manager(config_manager)
            if workspace.get_unique_file_key() is not None:
                app = workspace.get_single_app_file_manager(defaults).app
                return "".join(code for code in app.cell_manager.codes())

            files = list(flatten_files(workspace.files))
            entries = [
                f"{file.path}:{file.last_modified or 0.0}"
                for file in files
                if file.is_marimo_file
            ]
            return "\n".join(sorted(entries))

        source_code = None if mode == SessionMode.EDIT else _get_code()
        self._token_manager = TokenManager(
            mode=mode,
            auth_token=auth_token,
            source_code=source_code,
        )

        # Initialize resume strategy
        self._resume_strategy = create_resume_strategy(
            mode, self._repository, self._resolve_file_key
        )

        # Add recents tracking listener
        self.recents = RecentFilesManager()
        self._event_bus = SessionEventBus()
        self._event_bus.subscribe(RecentsTrackerListener(self.recents))

        # Initialize file watching components
        self._watcher_manager = FileWatcherManager()
        self.watch = watch
        self._file_change_coordinator = self._create_file_change_coordinator()

    @property
    def auth_token(self) -> AuthToken:
        """Get the auth token."""
        return self._token_manager.auth_token

    @property
    def skew_protection_token(self) -> SkewProtectionToken:
        """Get the skew protection token."""
        return self._token_manager.skew_protection_token

    @property
    def sessions(self) -> Mapping[SessionId, Session]:
        """Get all sessions as a dict."""
        return self._repository.sessions

    def app_manager(self, key: MarimoFileKey) -> AppFileManager:
        """Get the app manager for the given key."""
        defaults = AppDefaults.from_config_manager(self._config_manager)
        if self.mode is SessionMode.EDIT and not key.startswith(NEW_FILE):
            self.workspace.register_allowed_path(key)
        return self.workspace.load(key, defaults)

    @asynccontextmanager
    async def connection_lock(
        self, session_id: SessionId, file_key: MarimoFileKey
    ) -> AsyncIterator[None]:
        """Serialize reconnect decisions while a notebook is starting."""
        if self._closed:
            raise KernelStartupError("Session manager is shut down")
        key = (
            self._resolve_file_key(file_key) or file_key
            if self.mode == SessionMode.EDIT
            else session_id
        )
        lock = self._connection_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._connection_locks[key] = lock
        async with lock:
            if self.mode is SessionMode.EDIT:
                for pending in self._pending_for_file(file_key):
                    await asyncio.shield(pending.task)
            yield

    def _pending_for_file(
        self, file_key: MarimoFileKey
    ) -> list[_PendingSession]:
        path = self._resolve_file_key(file_key)
        return [
            pending
            for pending in self._pending.values()
            if (
                pending.snapshot.path == path
                if path is not None
                else pending.snapshot.initialization_id == file_key
            )
        ]

    def start_session(
        self, file_key: MarimoFileKey
    ) -> tuple[SessionSnapshot, bool]:
        """Atomically allocate or reuse an edit session, owned by this server."""
        if self._closed:
            raise KernelStartupError("Session manager is shut down")
        if self.mode is not SessionMode.EDIT:
            raise HTTPException(
                403, "Starting sessions requires an edit server"
            )
        self._cleanup_dead_sessions()
        sessions = self._repository.get_all_by_file_key(
            file_key, resolved_path=self._resolve_file_key(file_key)
        )
        pending = self._pending_for_file(file_key)
        if len(sessions) + len(pending) > 1:
            raise HTTPException(409, "Multiple sessions match this notebook")
        if sessions:
            session = sessions[0]
            if session.connection_state() is ConnectionState.CLOSED:
                raise HTTPException(409, "Session is closing")
            return SessionSnapshot.from_session(session), True
        if pending:
            pending[0].server_owned = True
            return pending[0].snapshot, True
        session_id = SessionId(str(uuid4()))
        entry = self._begin_session(session_id, None, {}, file_key, False)
        entry.server_owned = True
        return entry.snapshot, False

    def _begin_session(
        self,
        session_id: SessionId,
        session_consumer: SessionConsumer | None,
        query_params: SerializedQueryParams,
        file_key: MarimoFileKey,
        auto_instantiate: bool,
    ) -> _PendingSession:
        snapshot = SessionSnapshot(
            session_id=new_stable_session_id(),
            initialization_id=file_key,
            path=self._resolve_file_key(file_key),
            started_at=datetime.now(timezone.utc),
            status="starting",
        )

        def report_progress(phase: StartupPhase) -> None:
            pending.snapshot = replace(pending.snapshot, startup_phase=phase)
            self._notify_session_changed(snapshot.session_id)
            if session_consumer is not None:
                try:
                    session_consumer.notify(
                        serialize_kernel_message(
                            StartupProgressNotification(phase=phase)
                        )
                    )
                except Exception:
                    LOGGER.exception("Failed to deliver startup progress")

        task = asyncio.create_task(
            self._create_session(
                session_id,
                session_consumer,
                query_params,
                file_key,
                auto_instantiate,
                snapshot,
                report_progress,
            ),
            name=f"session.start.{session_id}",
        )
        pending = _PendingSession(task, snapshot)
        self._pending[session_id] = pending

        def finished(task: asyncio.Task[Session]) -> None:
            self._pending.pop(session_id, None)
            if task.cancelled():
                self._retain_session(replace(snapshot, status="terminated"))
            elif (error := task.exception()) is not None:
                if pending.server_owned:
                    LOGGER.error("Session startup failed", exc_info=error)
                self._retain_session(
                    replace(
                        snapshot,
                        status="failed",
                        error=KernelExitInfo(
                            None, "startup_failed", "Kernel failed to start"
                        ),
                    )
                )

        task.add_done_callback(finished)
        return pending

    async def create_session(
        self,
        session_id: SessionId,
        session_consumer: SessionConsumer,
        query_params: SerializedQueryParams,
        file_key: MarimoFileKey,
        auto_instantiate: bool,
    ) -> Session:
        """Return a ready session, retaining ownership during startup."""
        if self._closed:
            raise KernelStartupError("Session manager is shut down")
        existing = self._repository.get_sync(session_id)
        if existing is not None:
            return existing
        pending = self._pending.get(session_id)
        if pending is None:
            pending = self._begin_session(
                session_id,
                session_consumer,
                query_params,
                file_key,
                auto_instantiate,
            )
        pending.waiters += 1
        try:
            return await asyncio.shield(pending.task)
        finally:
            pending.waiters -= 1
            if (
                not pending.server_owned
                and pending.waiters == 0
                and not pending.task.done()
            ):
                # The last disconnected caller releases its connection lock
                # only after the abandoned launch has cleaned up.
                pending.task.cancel()
                await asyncio.gather(pending.task, return_exceptions=True)

    def is_session_starting(self, session_id: SessionId) -> bool:
        return session_id in self._pending

    async def _create_session(
        self,
        session_id: SessionId,
        session_consumer: SessionConsumer | None,
        query_params: SerializedQueryParams,
        file_key: MarimoFileKey,
        auto_instantiate: bool,
        snapshot: SessionSnapshot,
        on_progress: Callable[[StartupPhase], None],
    ) -> Session:
        """Create a new session."""
        LOGGER.debug("Creating new session for id %s", session_id)

        # Get app file manager
        defaults = AppDefaults.from_config_manager(self._config_manager)
        if self.mode is SessionMode.EDIT and not file_key.startswith(NEW_FILE):
            self.workspace.register_allowed_path(file_key)
        app_file_manager = await asyncio.to_thread(
            self.workspace.load, file_key, defaults
        )

        # Create the session
        from marimo._runtime.commands import AppMetadata
        from marimo._runtime.patches import extract_docstring_from_header

        extensions: list[SessionExtension] = [_SessionStateListener(self)]
        if self.watch:
            extensions.append(
                SessionFileWatcherExtension(
                    self._watcher_manager,
                    self._handle_file_change,
                )
            )

        session = await SessionImpl.create(
            stable_id=snapshot.session_id,
            started_at=snapshot.started_at,
            on_progress=on_progress,
            initialization_id=file_key,
            session_consumer=session_consumer,
            mode=self.mode,
            app_metadata=AppMetadata(
                query_params=query_params,
                filename=app_file_manager.path,
                cli_args=self.cli_args,
                argv=self.argv,
                app_config=app_file_manager.app.config,
                docstring=extract_docstring_from_header(
                    app_file_manager.app._app._header
                ),
            ),
            app_file_manager=app_file_manager,
            config_manager=self._config_manager,
            # EDIT mode runs the kernel in a subprocess (SharedMemoryStorage);
            # RUN mode runs it in a thread in the same process (InMemoryStorage).
            # AppHost-backed sessions override this with "shared_memory".
            virtual_file_storage=(
                "shared_memory"
                if self.mode == SessionMode.EDIT
                else "in_memory"
            ),
            redirect_console_to_browser=self.redirect_console_to_browser,
            ttl_seconds=self.ttl_seconds,
            auto_instantiate=auto_instantiate,
            extensions=extensions,
            sandbox=self.sandbox,
            app_host_context=AppHostContext(
                pool=self._app_host_pool, session_id=session_id
            )
            if self._app_host_pool
            else None,
        )

        if (
            session_consumer is None
            or session_consumer.connection_state() is ConnectionState.CLOSED
        ):
            try:
                session.instantiate(
                    InstantiateNotebookRequest(
                        object_ids=[], values=[], auto_run=False
                    ),
                    http_request=None,
                )
            except BaseException:
                session.close()
                raise

        # Publish the live session atomically with leaving pending state.
        self._pending.pop(session_id, None)
        self._repository.add_sync(session_id, session)
        self._notify_session_changed(session.stable_id)

        # Emit session created event (triggers file watcher attachment, recents, etc.)
        fire_and_forget(
            self._event_bus.emit_session_created(session),
            name="session.created",
        )

        return session

    def _create_file_change_coordinator(self) -> FileChangeCoordinator:
        """Create a file change coordinator."""
        reload_strategy = create_reload_strategy(
            self.mode, self._config_manager
        )
        return FileChangeCoordinator(reload_strategy)

    async def _handle_file_change(
        self, file_path: Path, session: Session
    ) -> None:
        await self._file_change_coordinator.handle_change(file_path, session)

    async def rename_session(
        self, session_id: SessionId, new_path: str
    ) -> tuple[bool, str | None]:
        """Handle renaming a file for a session.

        Returns:
            tuple[bool, Optional[str]]: (success, error_message)
        """
        from marimo._utils.http import HTTPException

        session = self.get_session(session_id)
        if not session:
            return False, "Session not found"

        old_path = session.app_file_manager.path

        try:
            await session.rename_path(new_path)
        except HTTPException as e:
            # HTTPException stores the message in detail, not in __str__
            return False, e.detail or str(e)
        except Exception as e:
            return False, str(e)

        renamed_path = session.app_file_manager.path
        if renamed_path is not None:
            self.workspace.register_allowed_path(renamed_path)

        # Emit the session notebook renamed event
        await self._event_bus.emit_session_notebook_renamed(session, old_path)

        return True, None

    async def trigger_file_change(self, path: str) -> None:
        """Handle a file change for all relevant sessions."""
        # Find all sessions associated with this file
        sessions_for_file = self._repository.get_by_file_path(path)

        if not sessions_for_file:
            return

        # Handle file change for each session
        for session in sessions_for_file:
            await self._file_change_coordinator.handle_change(
                Path(path), session
            )

    def get_session(self, session_id: SessionId) -> Session | None:
        """Get a session by ID, checking both direct and consumer IDs."""
        session = self._repository.get_sync(session_id)
        if session:
            return session

        # Search for kiosk sessions by consumer ID
        return self._repository.get_by_consumer_id(ConsumerId(session_id))

    def get_session_by_file_key(
        self, file_key: MarimoFileKey
    ) -> Session | None:
        """Get a session by file key."""
        return self._repository.get_by_file_key(
            file_key, resolved_path=self._resolve_file_key(file_key)
        )

    def get_session_snapshot(self, stable_id: str) -> SessionSnapshot | None:
        """Read live or retained terminal details using a stable session ID.

        Closing a session retains its details for five minutes without keeping
        the session, kernel, or document alive. Browser resumes preserve the ID.
        """
        self._discard_expired_snapshots()
        for snapshot in self.session_snapshots:
            if snapshot.session_id == stable_id:
                return snapshot
        retained = self._terminal_sessions.get(stable_id)
        return retained[1] if retained is not None else None

    @property
    def session_snapshots(self) -> list[SessionSnapshot]:
        """Observe live sessions and accepted starts without loading notebooks."""
        live = [
            SessionSnapshot.from_session(session)
            for session in self._repository.get_all()
            if session.connection_state() is not ConnectionState.CLOSED
        ]
        return [
            *live,
            *(pending.snapshot for pending in self._pending.values()),
        ]

    def _retain_session(self, snapshot: SessionSnapshot) -> None:
        self._discard_expired_snapshots()
        self._terminal_sessions[snapshot.session_id] = (
            monotonic() + _TERMINAL_RETENTION_SECONDS,
            snapshot,
        )
        self._notify_session_changed(snapshot.session_id)

    def _notify_session_changed(self, stable_id: str) -> None:
        subscribers = self._session_subscribers.get(stable_id)
        if not subscribers:
            return
        snapshot = self.get_session_snapshot(stable_id)
        if snapshot is None:
            return
        for queue in subscribers:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(snapshot)

    async def watch_session(
        self, stable_id: str
    ) -> AsyncGenerator[SessionSnapshot, None]:
        """Observe current state without owning the session's lifetime.

        Registration and the initial snapshot have no intervening await.
        Each observer retains only the latest state, including a terminal state.
        """
        snapshot = self.get_session_snapshot(stable_id)
        if snapshot is None:
            raise KeyError("Session not found")
        queue: asyncio.Queue[SessionSnapshot] = asyncio.Queue(maxsize=1)
        subscribers = self._session_subscribers.setdefault(stable_id, set())
        subscribers.add(queue)
        queue.put_nowait(snapshot)
        try:
            while True:
                snapshot = await queue.get()
                yield snapshot
                if snapshot.status in ("failed", "terminated"):
                    return
        finally:
            subscribers.remove(queue)
            if not subscribers:
                del self._session_subscribers[stable_id]

    def _discard_expired_snapshots(self) -> None:
        now = monotonic()
        self._terminal_sessions = {
            key: entry
            for key, entry in self._terminal_sessions.items()
            if entry[0] > now
        }

    def _resolve_file_key(self, file_key: MarimoFileKey) -> str | None:
        """Best-effort canonical absolute path for a file key.

        File keys can be workspace-relative, so resolving against the server
        CWD is wrong; the workspace owns the resolution. Returns None when
        the key has no backing file (untitled notebooks) or cannot be
        resolved (deleted file, path outside the workspace); session lookups
        then fall back to matching the key a session was created under.
        """
        from marimo._utils.http import HTTPException

        try:
            return self.workspace.resolve(file_key)
        except HTTPException:
            return None

    def maybe_resume_session(
        self, new_session_id: SessionId, file_key: MarimoFileKey
    ) -> Session | None:
        """Try to resume a session if one is resumable.

        If it is resumable, return the session and update the session id.
        """
        # Cleanup sessions with dead kernels first
        self._cleanup_dead_sessions()

        # Try to resume using the strategy
        resumed_session = self._resume_strategy.try_resume(
            new_session_id, file_key
        )

        if resumed_session:
            # Emit resume event (use new_session_id as both old and new since
            # the strategy already updated it)
            fire_and_forget(
                self._event_bus.emit_session_resumed(
                    resumed_session, new_session_id
                ),
                name="session.resumed",
            )

        return resumed_session

    def _cleanup_dead_sessions(self) -> None:
        """Remove sessions with dead kernels."""
        for session_id in list(self._repository.get_all_session_ids()):
            session = self._repository.get_sync(session_id)
            if session:
                if session.kernel_state() is KernelState.STOPPED:
                    self.close_session(session_id)

    def any_clients_connected(self, key: MarimoFileKey) -> bool:
        """Returns True if at least one client has an open socket."""
        if key.startswith(NEW_FILE):
            return False

        sessions_for_file = self._repository.get_by_file_path(key)
        return any(
            session.connection_state() == ConnectionState.OPEN
            for session in sessions_for_file
        )

    async def start_lsp_server(self) -> None:
        """Starts the lsp server if it is not already started.

        Doesn't start in run mode.
        """
        if self.mode == SessionMode.RUN:
            LOGGER.warning("Cannot start LSP server in run mode")
            return

        LOGGER.info("Starting LSP server...")
        alert = await self.lsp_server.start()

        if alert is not None:
            LOGGER.error(
                f"LSP server startup failed: {alert.title} - {alert.description}"
            )
            for session in self._repository.get_all():
                session.notify(alert, from_consumer_id=None)
            return
        else:
            LOGGER.info("LSP server started successfully")

    def close_session(self, session_id: SessionId) -> bool:
        """Close a session."""
        LOGGER.debug("Closing session %s", session_id)
        session = self._repository.remove_sync(session_id)
        if session is None:
            return False

        fire_and_forget(
            self._event_bus.emit_session_closed(session),
            name="session.closed",
        )

        # Capture a prior kernel failure before intentional shutdown can
        # replace its exit status with the signal used to close it.
        snapshot = self.get_session_snapshot(
            session.stable_id
        ) or SessionSnapshot.from_session(session)
        session.close()
        self._retain_session(
            replace(
                snapshot,
                status="failed"
                if snapshot.status == "failed"
                else "terminated",
            )
        )
        return True

    def close_all_sessions(self) -> None:
        """Close all sessions."""
        session_ids = self._repository.get_all_session_ids()
        LOGGER.debug("Closing all sessions (count: %s)", len(session_ids))
        for session_id in session_ids:
            self.close_session(session_id)
        LOGGER.debug("Closed all sessions.")

    async def shutdown(self) -> None:
        """Shutdown the session manager and stop all file watchers."""
        LOGGER.debug("Shutting down")
        self._closed = True
        pending = [entry.task for entry in self._pending.values()]
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        self.close_all_sessions()
        if self._app_host_pool is not None:
            self._app_host_pool.shutdown()
        self.lsp_server.stop()
        self._watcher_manager.stop_all()

    def should_send_code_to_frontend(self) -> bool:
        """Returns True if the server can send messages to the frontend."""
        return self.mode == SessionMode.EDIT or self.include_code

    def get_active_connection_count(self) -> int:
        """Get the number of sessions with active connections."""
        return len(self._repository.get_active_sessions())
