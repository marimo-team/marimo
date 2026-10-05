# Copyright 2026 Marimo. All rights reserved.
"""Session manager for coordinating multiple sessions.

The SessionManager maintains a mapping from client session IDs to sessions
and encapsulates state common to all sessions including auth tokens,
file watching, and LSP server management.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from weakref import WeakValueDictionary

from marimo import _loggers
from marimo._config.manager import MarimoConfigManager
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
from marimo._session.extensions.types import SessionExtension
from marimo._session.file_change_handler import (
    FileChangeCoordinator,
    create_reload_strategy,
)
from marimo._session.file_watcher_integration import (
    SessionFileWatcherExtension,
)
from marimo._session.managers.ipc import KernelStartupError
from marimo._session.model import ConnectionState, SessionMode
from marimo._session.session import Session, SessionImpl
from marimo._session.session_repository import SessionRepository
from marimo._session.startup import SessionStartup
from marimo._session.types import KernelState
from marimo._types.ids import ConsumerId, SessionId, StableSessionId
from marimo._utils.asyncio_utils import fire_and_forget
from marimo._utils.file_watcher import FileWatcherManager
from marimo._utils.ids import new_stable_session_id

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from marimo._session.notebook import AppFileManager

LOGGER = _loggers.marimo_logger()

_STARTUP_RECONNECT_SECONDS = 120.0


@dataclass
class _PendingSession:
    task: asyncio.Task[Session]
    startup: SessionStartup
    waiters: int = 0
    close_handle: asyncio.TimerHandle | None = None
    expired: bool = False


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
        self._pending: dict[str, _PendingSession] = {}
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
    def event_bus(self) -> SessionEventBus:
        """Lifecycle events for every session; see `SessionEventListener`."""
        return self._event_bus

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

    def connection_lock(
        self, session_id: SessionId, file_key: MarimoFileKey
    ) -> asyncio.Lock:
        """Serialize reconnect decisions while a notebook is starting."""
        if self._closed:
            raise KernelStartupError("Session manager is shut down")
        key = self._launch_key(session_id, file_key)
        lock = self._connection_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._connection_locks[key] = lock
        return lock

    def _launch_key(
        self, session_id: SessionId, file_key: MarimoFileKey
    ) -> str:
        """Names the kernel a connection is for, while it starts.

        An edit server runs one kernel per notebook, so the key is the
        file; a run server runs one per client, so the key is the client.
        """
        if self.mode == SessionMode.EDIT:
            return self._resolve_file_key(file_key) or file_key
        return session_id

    async def create_session(
        self,
        session_id: SessionId,
        session_consumer: SessionConsumer,
        query_params: SerializedQueryParams,
        file_key: MarimoFileKey,
        auto_instantiate: bool,
    ) -> Session:
        """Return a ready session, retaining ownership during startup."""
        key = self._launch_key(session_id, file_key)
        pending = await self._pending_launch(key)
        if pending is None:
            existing = self._repository.get_sync(session_id)
            if existing is not None:
                return existing
            pending = self._launch(
                key,
                session_id,
                new_stable_session_id(),
                query_params,
                file_key,
                auto_instantiate,
            )
        async with self._join(key, pending, session_consumer) as session:
            previous_id = self._repository.get_session_id(session)
            if (
                previous_id is None
                or session.connection_state() == ConnectionState.CLOSED
            ):
                if previous_id is not None:
                    self.close_session(previous_id)
                self._settle(key, pending)
                raise KernelStartupError("Session closed during startup")
            if session.room.main_consumer is not None:
                # The connection lock serializes attachment per key, so a
                # second main consumer means a caller bypassed it. The session
                # is in use either way, so its startup bookkeeping is done.
                self._settle(key, pending)
                raise RuntimeError("Session already has a main consumer")
            if previous_id != session_id:
                self._repository.update_session_id_sync(
                    previous_id, session_id
                )
            session.connect_consumer(session_consumer, main=True)
            self._settle(key, pending)
            return session

    async def start_session(
        self,
        file_key: MarimoFileKey,
        *,
        stable_id: StableSessionId,
        query_params: SerializedQueryParams | None = None,
        auto_instantiate: bool = False,
        observer: SessionConsumer | None = None,
    ) -> Session:
        """Return the notebook's session, starting one if it has none.

        Unlike `create_session`, nothing is attached: this is how a host
        starts a notebook on a client's behalf before any browser opens it.
        The caller names the session with `stable_id`, so a kernel that
        continues an earlier one keeps its identity; until a browser claims
        the session it is also routed under that id. The first browser to
        connect resumes the session by file key and becomes its main
        consumer. A launch already under way for the same notebook is
        awaited rather than repeated. `observer`, if given, receives
        startup progress while the kernel comes up.

        Only an edit server has one session per notebook to return, so a
        run server refuses: it serves an app to other people and starts a
        kernel for each of them.
        """
        if self.mode is not SessionMode.EDIT:
            raise KernelStartupError(
                "Only an edit server starts a session without a client"
            )
        session_id = SessionId(stable_id)
        key = self._launch_key(session_id, file_key)
        pending = await self._pending_launch(key)
        if pending is None:
            # A kernel that died stays registered until something looks
            # for it; it is no use to anyone, so it goes first.
            self._cleanup_dead_sessions()
            existing = self.get_session_by_file_key(file_key)
            if existing is not None:
                return existing
            pending = self._launch(
                key,
                session_id,
                stable_id,
                query_params or {},
                file_key,
                auto_instantiate,
            )
        async with self._join(key, pending, observer) as session:
            # The session is the caller's now. Browsers find it by file
            # key, and a reconnect window would only let an abandoned
            # waiter expire a session that the host owns.
            self._settle(key, pending)
            return session

    async def _pending_launch(self, key: str) -> _PendingSession | None:
        """The launch under way for `key`, if there is one.

        An expired launch is still releasing its resources; a new attempt
        must wait for that before it can begin, so this waits it out.
        """
        while True:
            if self._closed:
                raise KernelStartupError("Session manager is shut down")
            pending = self._pending.get(key)
            if pending is None or not pending.expired:
                return pending
            await asyncio.shield(
                asyncio.gather(pending.task, return_exceptions=True)
            )

    @contextlib.asynccontextmanager
    async def _join(
        self,
        key: str,
        pending: _PendingSession,
        observer: SessionConsumer | None,
    ) -> AsyncIterator[Session]:
        """Waits on a launch as one of its counted waiters.

        While anyone waits, the launch cannot expire. If the last waiter
        leaves without settling the launch, the reconnect timer is armed
        so an abandoned kernel does not outlive its startup. `observer`
        receives startup progress while the kernel comes up.
        """
        if pending.close_handle is not None:
            pending.close_handle.cancel()
            pending.close_handle = None
        pending.waiters += 1
        try:
            if observer is None:
                session = await asyncio.shield(pending.task)
            else:
                with pending.startup.subscribe(observer):
                    session = await asyncio.shield(pending.task)
            if self._closed:
                raise KernelStartupError("Session manager is shut down")
            yield session
        finally:
            pending.waiters -= 1
            if (
                pending.waiters == 0
                and self._pending.get(key) is pending
                and not self._closed
            ):
                # Nobody has seen an unattached launch, so a long session
                # TTL must not keep abandoned kernels alive.
                pending.close_handle = asyncio.get_running_loop().call_later(
                    min(self.ttl_seconds, _STARTUP_RECONNECT_SECONDS)
                    if self.ttl_seconds is not None
                    else _STARTUP_RECONNECT_SECONDS,
                    self._expire_startup,
                    key,
                    pending,
                )

    def _settle(self, key: str, pending: _PendingSession) -> None:
        """Ends a launch's startup bookkeeping: its session has an owner."""
        if self._pending.get(key) is pending:
            self._pending.pop(key)

    def _launch(
        self,
        key: str,
        session_id: SessionId,
        stable_id: StableSessionId,
        query_params: SerializedQueryParams,
        file_key: MarimoFileKey,
        auto_instantiate: bool,
    ) -> _PendingSession:
        """Begin creating a session and record the launch under `key`."""
        startup = SessionStartup()
        task = asyncio.create_task(
            self._create_session(
                session_id,
                stable_id,
                query_params,
                file_key,
                auto_instantiate,
                startup,
            ),
            name=f"session.start.{session_id}",
        )
        pending = _PendingSession(task, startup)
        self._pending[key] = pending

        def finished(task: asyncio.Task[Session]) -> None:
            # Failed launches can be retried; successful ones await attachment.
            if task.cancelled() or task.exception() is not None:
                if pending.close_handle is not None:
                    pending.close_handle.cancel()
                if self._pending.get(key) is pending:
                    self._pending.pop(key)

        task.add_done_callback(finished)
        return pending

    def _expire_startup(self, key: str, pending: _PendingSession) -> None:
        pending.close_handle = None
        if not pending.task.done():
            pending.expired = True
            pending.task.cancel()
            return
        self._pending.pop(key, None)
        if pending.task.cancelled() or pending.task.exception() is not None:
            return
        session = pending.task.result()
        if session.room.size == 0:
            orphan_id = self._repository.get_session_id(session)
            if orphan_id is not None:
                self.close_session(orphan_id)

    def is_session_starting(
        self, session_id: SessionId, file_key: MarimoFileKey
    ) -> bool:
        return self._launch_key(session_id, file_key) in self._pending

    async def _create_session(
        self,
        session_id: SessionId,
        stable_id: StableSessionId,
        query_params: SerializedQueryParams,
        file_key: MarimoFileKey,
        auto_instantiate: bool,
        startup: SessionStartup,
    ) -> Session:
        """Create a new session."""
        LOGGER.debug("Creating new session for id %s", session_id)

        # Get app file manager
        defaults = AppDefaults.from_config_manager(self._config_manager)
        if self.mode is SessionMode.EDIT and not file_key.startswith(NEW_FILE):
            self.workspace.register_allowed_path(file_key)
        app_file_manager = self.workspace.load(file_key, defaults)

        # Create the session
        from marimo._runtime.commands import AppMetadata
        from marimo._runtime.patches import extract_docstring_from_header

        extensions: list[SessionExtension] = []
        if self.watch:
            extensions.append(
                SessionFileWatcherExtension(
                    self._watcher_manager,
                    self._handle_file_change,
                )
            )

        session = await SessionImpl.create(
            stable_id=stable_id,
            initialization_id=file_key,
            startup=startup,
            session_consumer=None,
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

        # Add to repository
        self._repository.add_sync(session_id, session)

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

    def get_session_id(self, session: Session) -> SessionId | None:
        """The routing id `session` is registered under, if it is."""
        return self._repository.get_session_id(session)

    def get_session_by_file_key(
        self, file_key: MarimoFileKey
    ) -> Session | None:
        """Get a session by file key."""
        return self._repository.get_by_file_key(
            file_key, resolved_path=self._resolve_file_key(file_key)
        )

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

        for key, pending in list(self._pending.items()):
            if (
                pending.task.done()
                and not pending.task.cancelled()
                and pending.task.exception() is None
                and pending.task.result() is session
            ):
                if pending.close_handle is not None:
                    pending.close_handle.cancel()
                self._pending.pop(key)

        fire_and_forget(
            self._event_bus.emit_session_closed(session),
            name="session.closed",
        )

        session.close()
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
        for entry in self._pending.values():
            if entry.close_handle is not None:
                entry.close_handle.cancel()
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        self._pending.clear()
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
