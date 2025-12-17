# Copyright 2024 Marimo. All rights reserved.
"""File watcher integration for sessions.

Provides clean abstraction for attaching/detaching file watchers to sessions
without leaking implementation details or monkey-patching.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from marimo import _loggers
from marimo._server.sessions.events import SessionEventListener
from marimo._server.sessions.session import Session
from marimo._server.sessions.session_repository import SessionRepository
from marimo._types.ids import SessionId
from marimo._utils import async_path
from marimo._utils.file_watcher import FileWatcherManager

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Awaitable


class SessionFileWatcherLifecycle:
    """Manages file watcher lifecycle for sessions."""

    def __init__(
        self,
        watcher_manager: FileWatcherManager,
        file_change_callback: Callable[[Path, Session], Awaitable[None]],
        repository: SessionRepository,
    ) -> None:
        """Initialize the file watcher lifecycle manager.

        Args:
            watcher_manager: The underlying file watcher manager
            file_change_callback: Callback to invoke when files change
            repository: Session repository for ID lookups
        """
        self._watcher_manager = watcher_manager
        self._file_change_callback = file_change_callback
        self._repository = repository
        # Store callbacks by session object instead of ID
        # since ID may change
        self._session_callbacks: dict[
            Session, Callable[[Path], Awaitable[None]]
        ] = {}

    def attach(self, session: Session) -> None:
        """Attach a file watcher to a session.

        Args:
            session: The session to attach a file watcher to
        """
        session_id = self._repository.get_session_id(session)
        if not session.app_file_manager.path:
            LOGGER.debug(
                "Session %s has no file path, skipping file watcher",
                session_id,
            )
            return

        # Create callback for this specific session
        async def on_file_changed(path: Path) -> None:
            # Skip if the session does not relate to the file
            if session.app_file_manager.path != await async_path.abspath(path):
                return

            # Use the centralized file change handler
            await self._file_change_callback(path, session)

        # Store the callback
        self._session_callbacks[session] = on_file_changed

        # Register with the watcher manager
        self._watcher_manager.add_callback(
            Path(session.app_file_manager.path), on_file_changed
        )

        LOGGER.debug(
            "Attached file watcher for session %s at path %s",
            session_id,
            session.app_file_manager.path,
        )

    def detach(self, session: Session) -> None:
        """Detach a file watcher from a session.

        Args:
            session: The session to detach the file watcher from
        """
        session_id = self._repository.get_session_id(session)
        if not session.app_file_manager.path:
            return

        callback = self._session_callbacks.get(session)
        if callback is None:
            LOGGER.debug(
                "No file watcher callback found for session %s",
                session_id,
            )
            return

        # Remove from watcher manager
        self._watcher_manager.remove_callback(
            Path(session.app_file_manager.path), callback
        )

        # Remove from our registry
        del self._session_callbacks[session]

        LOGGER.debug(
            "Detached file watcher for session %s from path %s",
            session_id,
            session.app_file_manager.path,
        )

    def update(self, session: Session, old_path: Path, new_path: Path) -> None:
        """Update file watcher when a session's file path changes.

        Args:
            session: The session whose path changed
            old_path: The old file path
            new_path: The new file path
        """
        session_id = self._repository.get_session_id(session)
        callback = self._session_callbacks.get(session)
        if callback:
            # Remove old watcher
            self._watcher_manager.remove_callback(old_path, callback)

        # Attach new watcher
        self.attach(session)

        LOGGER.debug(
            "Updated file watcher for session %s from %s to %s",
            session_id,
            old_path,
            new_path,
        )

    def stop_all(self) -> None:
        """Stop all file watchers."""
        self._watcher_manager.stop_all()
        self._session_callbacks.clear()


class FileWatcherAttachmentListener(SessionEventListener):
    """Event listener that attaches/detaches file watchers on session lifecycle events."""

    def __init__(
        self,
        file_watcher_lifecycle: SessionFileWatcherLifecycle,
        enabled: bool,
    ) -> None:
        """Initialize the file watcher attachment listener.

        Args:
            file_watcher_lifecycle: The file watcher lifecycle manager
            enabled: Whether file watching is enabled
        """
        self._lifecycle = file_watcher_lifecycle
        self._enabled = enabled

    async def on_session_created(self, session: Session) -> None:
        """Attach file watcher when a session is created."""
        if self._enabled:
            self._lifecycle.attach(session)

    async def on_session_closed(self, session: Session) -> None:
        """Detach file watcher when a session is closed."""
        if self._enabled:
            self._lifecycle.detach(session)

    async def on_session_resumed(
        self, session: Session, old_id: SessionId
    ) -> None:
        """No action needed on resume - watcher remains attached."""
        pass
