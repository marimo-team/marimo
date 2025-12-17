# Copyright 2024 Marimo. All rights reserved.
"""Session manager for coordinating multiple sessions.

The SessionManager maintains a mapping from client session IDs to sessions
and encapsulates state common to all sessions including auth tokens,
file watching, and LSP server management.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from marimo import _loggers
from marimo._config.manager import MarimoConfigManager
from marimo._messaging.ops import (
    Reload,
    UpdateCellCodes,
    UpdateCellIdsRequest,
)
from marimo._runtime.requests import (
    DeleteCellRequest,
    SerializedCLIArgs,
    SerializedQueryParams,
    SyncGraphRequest,
)
from marimo._server.exceptions import InvalidSessionException
from marimo._server.file_router import AppFileRouter, MarimoFileKey
from marimo._server.lsp import LspServer
from marimo._server.model import ConnectionState, SessionConsumer, SessionMode
from marimo._server.notebook import AppFileManager
from marimo._server.recents import RecentFilesManager
from marimo._server.sessions.session import Session, SessionImpl
from marimo._server.tokens import AuthToken, SkewProtectionToken
from marimo._types.ids import ConsumerId, SessionId
from marimo._utils import async_path
from marimo._utils.file_watcher import FileWatcherManager

LOGGER = _loggers.marimo_logger()


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
        self.file_router = file_router
        self.mode = mode
        self.quiet = quiet
        self.sessions: dict[SessionId, Session] = {}
        self.include_code = include_code
        self.ttl_seconds = ttl_seconds
        self.lsp_server = lsp_server
        self.file_change_handler = SessionFileChangeHandler(
            self, config_manager
        )
        self.watcher_manager = FileWatcherManager()
        self.watch = watch
        self.recents = RecentFilesManager()
        self.cli_args = cli_args
        self.argv = argv
        self.redirect_console_to_browser = redirect_console_to_browser

        # We should access the config_manager from the session if possible
        # since this will contain config-level overrides
        self._config_manager = config_manager

        def _get_code() -> str:
            app = file_router.get_single_app_file_manager(
                default_width=self._config_manager.default_width,
                default_auto_download=self._config_manager.default_auto_download,
                default_sql_output=self._config_manager.default_sql_output,
            ).app
            return "".join(code for code in app.cell_manager.codes())

        # Auth token and Skew-protection token
        if mode == SessionMode.EDIT:
            # In edit mode, if no auth token is provided,
            # generate a random token
            self.auth_token = (
                AuthToken.random() if auth_token is None else auth_token
            )
            self.skew_protection_token = SkewProtectionToken.random()
        else:
            source_code = _get_code()
            # Because run-mode is read-only and we could have multiple
            # servers for the same app (going to sleep or autoscaling),
            # we default to a token based on the app's code
            self.auth_token = (
                AuthToken.from_code(source_code)
                if auth_token is None
                else auth_token
            )
            self.skew_protection_token = SkewProtectionToken.from_code(
                source_code
            )

    def app_manager(self, key: MarimoFileKey) -> AppFileManager:
        """
        Get the app manager for the given key.
        """
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
    ) -> Session:
        """Create a new session"""
        LOGGER.debug("Creating new session for id %s", session_id)
        if session_id not in self.sessions:
            app_file_manager = self.file_router.get_file_manager(
                file_key,
                default_width=self._config_manager.default_width,
                default_auto_download=self._config_manager.default_auto_download,
                default_sql_output=self._config_manager.default_sql_output,
            )

            if app_file_manager.path:
                self.recents.touch(app_file_manager.path)

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
            )
            self.sessions[session_id] = session

            # Start file watcher if enabled
            if self.watch and app_file_manager.path:
                self._start_file_watcher_for_session(session)

        return self.sessions[session_id]

    def _start_file_watcher_for_session(self, session: Session) -> None:
        """Start a file watcher for a session."""
        if not session.app_file_manager.path:
            return

        async def on_file_changed(path: Path) -> None:
            # Skip if the session does not relate to the file
            if session.app_file_manager.path != await async_path.abspath(path):
                return

            # Use the centralized file change handler
            await self.file_change_handler.handle_file_change(
                str(path), [session]
            )

        session._unsubscribe_file_watcher_ = on_file_changed  # type: ignore

        self.watcher_manager.add_callback(
            Path(session.app_file_manager.path), on_file_changed
        )

    def handle_file_rename_for_watch(
        self, session_id: SessionId, prev_path: Optional[str], new_path: str
    ) -> tuple[bool, Optional[str]]:
        """Handle renaming a file for a session.

        Returns:
            tuple[bool, Optional[str]]: (success, error_message)
        """
        session = self.get_session(session_id)
        if not session:
            return False, "Session not found"

        if not os.path.exists(new_path):
            return False, f"File {new_path} does not exist"

        if not session.app_file_manager.path:
            return False, "Session has no associated file"

        # Handle rename for session cache
        if session.session_cache_manager:
            session.session_cache_manager.rename_path(new_path)

        try:
            if self.watch:
                # Remove the old file watcher if it exists
                if prev_path:
                    self.watcher_manager.remove_callback(
                        Path(prev_path),
                        session._unsubscribe_file_watcher_,  # type: ignore
                    )

                # Add a watcher for the new path if needed
                self._start_file_watcher_for_session(session)

            return True, None

        except Exception as e:
            LOGGER.error(f"Error handling file rename: {e}")

            if self.watch:
                self._start_file_watcher_for_session(session)
            return False, str(e)

    async def handle_file_change(self, path: str) -> None:
        """Handle a file change."""
        await self.file_change_handler.handle_file_change(
            path, list(self.sessions.values())
        )

    def get_session(self, session_id: SessionId) -> Optional[Session]:
        session = self.sessions.get(session_id)
        if session:
            return session

        # Search for kiosk sessions
        for session in self.sessions.values():
            if ConsumerId(session_id) in session.consumers.values():
                return session

        return None

    def get_session_by_file_key(
        self, file_key: MarimoFileKey
    ) -> Optional[Session]:
        for session in self.sessions.values():
            if (
                session.initialization_id == file_key
                or session.app_file_manager.path == os.path.abspath(file_key)
            ):
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

        # Cleanup sessions with dead kernels; materializing as a list because
        # close_sessions mutates self.sessions
        for session_id, session in list(self.sessions.items()):
            task = session.kernel_manager.kernel_task
            if task is not None and not task.is_alive():
                self.close_session(session_id)

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
            if new_session_id != session_id and session_id in self.sessions:
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
            for session in self.sessions.values():
                session.write_operation(alert, from_consumer_id=None)
            return
        else:
            LOGGER.info("LSP server started successfully")

    def close_session(self, session_id: SessionId) -> bool:
        """Close a session and remove its file watcher if it has one."""
        LOGGER.debug("Closing session %s", session_id)
        session = self.get_session(session_id)
        if session is None:
            return False

        # Remove the file watcher callback for this session
        if session.app_file_manager.path and self.watch:
            self.watcher_manager.remove_callback(
                Path(session.app_file_manager.path),
                session._unsubscribe_file_watcher_,  # type: ignore
            )

        session.close()
        if session_id in self.sessions:
            del self.sessions[session_id]
        return True

    def close_all_sessions(self) -> None:
        LOGGER.debug("Closing all sessions (sessions: %s)", self.sessions)
        for session in self.sessions.values():
            session.close()
        LOGGER.debug("Closed all sessions.")
        self.sessions = {}

    def shutdown(self) -> None:
        """Shutdown the session manager and stop all file watchers."""
        LOGGER.debug("Shutting down")
        self.close_all_sessions()
        self.lsp_server.stop()
        self.watcher_manager.stop_all()

    def should_send_code_to_frontend(self) -> bool:
        """Returns True if the server can send messages to the frontend."""
        return self.mode == SessionMode.EDIT or self.include_code

    def get_active_connection_count(self) -> int:
        return len(
            [
                session
                for session in self.sessions.values()
                if session.connection_state() == ConnectionState.OPEN
            ]
        )


class SessionFileChangeHandler:
    def __init__(
        self,
        session_manager: SessionManager,
        config_manager: MarimoConfigManager,
    ) -> None:
        self.session_manager = session_manager
        self.config_manager = config_manager
        # Track ongoing file change operations to prevent duplicates
        self._file_change_locks: dict[str, asyncio.Lock] = {}

    async def handle_file_change(
        self, file_path: str, sessions: list[Session]
    ) -> None:
        """Handle file changes for marimo notebooks.

        This method reloads the notebook and sends appropriate operations
        to the frontend when a marimo file is modified.
        """
        abs_file_path = await async_path.abspath(file_path)

        # Use a lock to prevent concurrent processing of the same file
        if abs_file_path not in self._file_change_locks:
            self._file_change_locks[abs_file_path] = asyncio.Lock()

        async with self._file_change_locks[abs_file_path]:
            # Find all sessions associated with this file
            sessions_for_file: list[Session] = []
            for s in sessions:
                if s.app_file_manager.path == abs_file_path:
                    sessions_for_file.append(s)

            if not sessions_for_file:
                # No active session for this file
                return

            if len(sessions_for_file) > 1:
                LOGGER.error(
                    f"Only one session should exist for a file: {abs_file_path}"
                )

            self._handle_file_change(
                abs_file_path,
                sessions_for_file[0],
            )

    def _handle_file_change(
        self,
        file_path: str,
        session: Session,
    ) -> None:
        LOGGER.debug(f"{file_path} was modified, handling {session}")

        # Check if the file content matches the last save
        # to avoid reloading our own writes
        if session.app_file_manager.file_content_matches_last_save():
            LOGGER.debug(
                f"File {file_path} content matches last save, skipping reload"
            )
            return

        # Reload the file manager to get the latest code
        try:
            changed_cell_ids = session.app_file_manager.reload()
        except Exception as e:
            # If there are syntax errors, we just skip
            # and don't send the changes
            LOGGER.error(f"Error loading file: {e}")
            return

        # In run mode, we just call Reload()
        if self.session_manager.mode == SessionMode.RUN:
            session.write_operation(Reload(), from_consumer_id=None)
            return

        # Get the latest codes
        codes = list(session.app_file_manager.app.cell_manager.codes())
        cell_ids = list(session.app_file_manager.app.cell_manager.cell_ids())

        LOGGER.info(
            f"File changed: {file_path}. num_cell_ids: {len(cell_ids)}, num_codes: {len(codes)}, changed_cell_ids: {changed_cell_ids}"
        )

        # Send the updated cell ids and codes to the frontend
        session.write_operation(
            UpdateCellIdsRequest(cell_ids=cell_ids),
            from_consumer_id=None,
        )

        # Check if we should auto-run cells based on config
        watcher_on_save = self.config_manager.get_config()["runtime"][
            "watcher_on_save"
        ]
        should_autorun = watcher_on_save == "autorun"
        deleted = {
            cell_id for cell_id in changed_cell_ids if cell_id not in cell_ids
        }

        # Auto-run cells if configured
        if should_autorun:
            changed_cell_ids_list = list(changed_cell_ids - deleted)
            cells = dict(zip(cell_ids, codes))

            session.put_control_request(
                SyncGraphRequest(
                    cells=cells,
                    run_ids=changed_cell_ids_list,
                    delete_ids=list(deleted),
                ),
                from_consumer_id=None,
            )
        else:
            for to_delete in deleted:
                session.put_control_request(
                    DeleteCellRequest(cell_id=to_delete),
                    from_consumer_id=None,
                )
            session.write_operation(
                UpdateCellCodes(
                    cell_ids=cell_ids,
                    codes=codes,
                    code_is_stale=True,
                ),
                from_consumer_id=None,
            )
