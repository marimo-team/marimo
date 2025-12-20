# Copyright 2024 Marimo. All rights reserved.
"""Session manager for coordinating multiple sessions.

The SessionManager maintains a mapping from client session IDs to sessions
and encapsulates state common to all sessions including auth tokens,
file watching, and LSP server management.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Optional, TypeVar

from marimo import _loggers
from marimo._config.manager import MarimoConfigManager
from marimo._runtime.requests import (
    SerializedCLIArgs,
    SerializedQueryParams,
)
from marimo._server.file_router import AppFileRouter, MarimoFileKey
from marimo._server.lsp import LspServer
from marimo._server.model import ConnectionState, SessionConsumer, SessionMode
from marimo._server.notebook import AppFileManager
from marimo._server.recents import RecentFilesManager
from marimo._server.sessions.events import SessionEventBus
from marimo._server.sessions.file_change_handler import (
    FileChangeCoordinator,
    create_reload_strategy,
)
from marimo._server.sessions.file_watcher_integration import (
    FileWatcherAttachmentListener,
    SessionFileWatcherLifecycle,
)
from marimo._server.sessions.listeners import RecentsTrackerListener
from marimo._server.sessions.resume_strategies import create_resume_strategy
from marimo._server.sessions.session import Session, SessionImpl
from marimo._server.sessions.session_repository import SessionRepository
from marimo._server.sessions.token_manager import TokenManager
from marimo._server.sessions.types import KernelState
from marimo._server.tokens import AuthToken, SkewProtectionToken
from marimo._types.ids import ConsumerId, SessionId
from marimo._utils.async_path import AsyncPath
from marimo._utils.file_watcher import FileWatcherManager

if TYPE_CHECKING:
    from collections.abc import Awaitable, Coroutine, Mapping

LOGGER = _loggers.marimo_logger()


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
        file_router: AppFileRouter,
        mode: SessionMode,
        quiet: bool,
        include_code: bool,
        lsp_server: LspServer,
        config_manager: MarimoConfigManager,
        cli_args: SerializedCLIArgs,
        argv: list[str] | None,
        auth_token: Optional[AuthToken],
        redirect_console_to_browser: bool,
        ttl_seconds: Optional[int],
        watch: bool = False,
    ) -> None:
        # Core configuration
        self.file_router = file_router
        self.mode = mode
        self.quiet = quiet
        self.include_code = include_code
        self.ttl_seconds = ttl_seconds
        self.lsp_server = lsp_server
        self.cli_args = cli_args
        self.argv = argv
        self.redirect_console_to_browser = redirect_console_to_browser
        self._config_manager = config_manager

        self._repository = SessionRepository()

        def _get_code() -> str:
            app = file_router.get_single_app_file_manager(
                default_width=config_manager.default_width,
                default_auto_download=config_manager.default_auto_download,
                default_sql_output=config_manager.default_sql_output,
            ).app
            return "".join(code for code in app.cell_manager.codes())

        source_code = None if mode == SessionMode.EDIT else _get_code()
        self._token_manager = TokenManager(
            mode=mode,
            auth_token=auth_token,
            source_code=source_code,
        )

        # Initialize resume strategy
        self._resume_strategy = create_resume_strategy(mode, self._repository)

        # Initialize event bus and listeners
        self._event_bus = SessionEventBus()

        # Add recents tracking listener
        self.recents = RecentFilesManager()
        self._event_bus.subscribe(RecentsTrackerListener(self.recents))

        # Initialize file watching components if enabled
        self.watch = watch
        if watch:
            self._setup_file_watching()

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

    def _setup_file_watching(self) -> None:
        """Set up file watching components."""
        # Create file watcher manager
        self.watcher_manager = FileWatcherManager()

        # Create file change coordinator with appropriate reload strategy
        reload_strategy = create_reload_strategy(
            self.mode, self._config_manager
        )
        self._file_change_coordinator = FileChangeCoordinator(reload_strategy)

        # Create file watcher lifecycle manager
        async def on_file_change(path: Path, session: Session) -> None:
            await self._file_change_coordinator.handle_change(path, session)

        self._file_watcher_lifecycle = SessionFileWatcherLifecycle(
            self.watcher_manager, on_file_change, self._repository
        )

        # Register file watcher attachment listener
        self._event_bus.subscribe(
            FileWatcherAttachmentListener(
                self._file_watcher_lifecycle, enabled=True
            )
        )

    def app_manager(self, key: MarimoFileKey) -> AppFileManager:
        """Get the app manager for the given key."""
        return self.file_router.get_file_manager(
            key,
            default_width=self._config_manager.default_width,
            default_auto_download=self._config_manager.default_auto_download,
            default_sql_output=self._config_manager.default_sql_output,
        )

    def create_session(
        self,
        session_id: SessionId,
        session_consumer: SessionConsumer,
        query_params: SerializedQueryParams,
        file_key: MarimoFileKey,
        auto_instantiate: bool,
    ) -> Session:
        """Create a new session."""
        LOGGER.debug("Creating new session for id %s", session_id)

        # Check if session already exists
        existing = self._repository.get_sync(session_id)
        if existing:
            return existing

        # Get app file manager
        app_file_manager = self.file_router.get_file_manager(
            file_key,
            default_width=self._config_manager.default_width,
            default_auto_download=self._config_manager.default_auto_download,
            default_sql_output=self._config_manager.default_sql_output,
        )

        # Create the session
        from marimo._runtime.requests import AppMetadata

        session = SessionImpl.create(
            initialization_id=file_key,
            session_consumer=session_consumer,
            mode=self.mode,
            app_metadata=AppMetadata(
                query_params=query_params,
                filename=app_file_manager.path,
                cli_args=self.cli_args,
                argv=self.argv,
                app_config=app_file_manager.app.config,
            ),
            app_file_manager=app_file_manager,
            config_manager=self._config_manager,
            virtual_files_supported=True,
            redirect_console_to_browser=self.redirect_console_to_browser,
            ttl_seconds=self.ttl_seconds,
            auto_instantiate=auto_instantiate,
        )

        # Add to repository
        self._repository.add_sync(session_id, session)

        # Emit session created event (triggers file watcher attachment, recents, etc.)
        run_async(self._event_bus.emit_session_created(session))

        return session

    async def handle_file_rename_for_watch(
        self, session_id: SessionId, prev_path: Optional[str], new_path: str
    ) -> tuple[bool, Optional[str]]:
        """Handle renaming a file for a session.

        Returns:
            tuple[bool, Optional[str]]: (success, error_message)
        """
        session = self.get_session(session_id)
        if not session:
            return False, "Session not found"

        if not await AsyncPath(new_path).exists():
            return False, f"File {new_path} does not exist"

        if not session.app_file_manager.path:
            return False, "Session has no associated file"

        await session.rename_path(new_path)

        try:
            if self.watch and self._file_watcher_lifecycle:
                # Update the file watcher
                if prev_path:
                    self._file_watcher_lifecycle.update(
                        session, Path(prev_path), Path(new_path)
                    )
                else:
                    self._file_watcher_lifecycle.attach(session)

            return True, None

        except Exception as e:
            LOGGER.error(f"Error handling file rename: {e}")

            if self.watch and hasattr(self, "_file_watcher_lifecycle"):
                self._file_watcher_lifecycle.attach(session)
            return False, str(e)

    async def handle_file_change(self, path: str) -> None:
        """Handle a file change for all relevant sessions."""
        # Find all sessions associated with this file
        sessions_for_file = self._repository.get_by_file_path(path)

        if not sessions_for_file:
            return

        # Handle file change for each session
        if self.watch and hasattr(self, "_file_watcher_lifecycle"):
            from marimo._server.sessions.file_change_handler import (
                FileChangeCoordinator,
            )

            reload_strategy = create_reload_strategy(
                self.mode, self._config_manager
            )
            coordinator = FileChangeCoordinator(reload_strategy)

            for session in sessions_for_file:
                await coordinator.handle_change(Path(path), session)

    def get_session(self, session_id: SessionId) -> Optional[Session]:
        """Get a session by ID, checking both direct and consumer IDs."""
        session = self._repository.get_sync(session_id)
        if session:
            return session

        # Search for kiosk sessions by consumer ID
        return self._repository.get_by_consumer_id(ConsumerId(session_id))

    def get_session_by_file_key(
        self, file_key: MarimoFileKey
    ) -> Optional[Session]:
        """Get a session by file key."""
        return self._repository.get_by_file_key(file_key)

    def maybe_resume_session(
        self, new_session_id: SessionId, file_key: MarimoFileKey
    ) -> Optional[Session]:
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
            run_async(
                self._event_bus.emit_session_resumed(
                    resumed_session, new_session_id
                )
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
        if key.startswith(AppFileRouter.NEW_FILE):
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
                session.write_operation(alert, from_consumer_id=None)
            return
        else:
            LOGGER.info("LSP server started successfully")

    def close_session(self, session_id: SessionId) -> bool:
        """Close a session."""
        LOGGER.debug("Closing session %s", session_id)
        session = self._repository.remove_sync(session_id)
        if session is None:
            return False

        run_async(self._event_bus.emit_session_closed(session))

        session.close()
        return True

    def close_all_sessions(self) -> None:
        """Close all sessions."""
        session_ids = self._repository.get_all_session_ids()
        LOGGER.debug("Closing all sessions (count: %s)", len(session_ids))
        for session_id in session_ids:
            self.close_session(session_id)
        LOGGER.debug("Closed all sessions.")

    def shutdown(self) -> None:
        """Shutdown the session manager and stop all file watchers."""
        LOGGER.debug("Shutting down")
        self.close_all_sessions()
        self.lsp_server.stop()
        if self.watch and hasattr(self, "watcher_manager"):
            self.watcher_manager.stop_all()

    def should_send_code_to_frontend(self) -> bool:
        """Returns True if the server can send messages to the frontend."""
        return self.mode == SessionMode.EDIT or self.include_code

    def get_active_connection_count(self) -> int:
        """Get the number of sessions with active connections."""
        return len(self._repository.get_active_sessions())


T = TypeVar("T")


def run_async(coro: Coroutine[None, None, T] | Awaitable[T]) -> T:
    """Run an async coroutine, handling various event loop states.

    1. Event loop is running: create a task
    2. Event loop exists but not running: run_until_complete
    3. No event loop: create one with asyncio.run
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a task and return it (fire and forget)
            # Note: This doesn't wait for completion
            task = asyncio.create_task(coro)  # type: ignore
            return task  # type: ignore
        else:
            # Run to completion
            return loop.run_until_complete(coro)  # type: ignore
    except RuntimeError:
        # No event loop exists, create one
        return asyncio.run(coro)  # type: ignore
