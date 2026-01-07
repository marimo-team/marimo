# Copyright 2026 Marimo. All rights reserved.
"""File watcher integration for sessions.

Provides clean abstraction for attaching/detaching file watchers to sessions
without leaking implementation details or monkey-patching.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from marimo import _loggers
from marimo._session.events import (
    SessionEventBus,
    SessionEventListener,
)
from marimo._session.extensions.types import SessionExtension
from marimo._session.session import Session
from marimo._utils.file_watcher import FileWatcherManager
from marimo._utils.paths import normalize_path

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Awaitable


class SessionFileWatcherExtension(SessionExtension, SessionEventListener):
    """Manages file watcher lifecycle for sessions."""

    def __init__(
        self,
        watcher_manager: FileWatcherManager,
        on_change_callback: Callable[[Path, Session], Awaitable[None]],
    ) -> None:
        """Initialize the file watcher extension.

        Args:
            watcher_manager: The underlying file watcher manager
            on_change_callback: The callback to invoke when a file changes
        """
        self._watcher_manager = watcher_manager
        self._event_bus: SessionEventBus | None = None
        self._session: Session | None = None
        self._on_change_callback = on_change_callback

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        """Attach the file watcher extension to a session."""
        self._event_bus = event_bus
        self._event_bus.subscribe(self)
        self._session = session

        if not session.app_file_manager.path:
            return

        # Register with the watcher manager
        self._watcher_manager.add_callback(
            Path(session.app_file_manager.path), self._handle_file_change
        )

        LOGGER.info(
            "Attached file watcher for session %s at path %s",
            session.initialization_id,
            session.app_file_manager.path,
        )

    async def _handle_file_change(self, path: Path) -> None:
        """Handle a file change."""
        if not self._session:
            return

        await self._on_change_callback(path, self._session)

    def on_detach(self) -> None:
        """Detach the file watcher extension from a session."""
        if not self._session:
            return

        if not self._session.app_file_manager.path:
            return

        # Remove from watcher manager
        self._watcher_manager.remove_callback(
            self._canonicalize_path(self._session.app_file_manager.path),
            self._handle_file_change,
        )

        LOGGER.info(
            "Detached file watcher for session %s from path %s",
            self._session.initialization_id,
            self._session.app_file_manager.path,
        )

    def _canonicalize_path(self, path: str) -> Path:
        """Canonicalize a path without resolving symlinks."""
        return normalize_path(Path(path))

    async def on_session_notebook_renamed(
        self, session: Session, old_path: str | None
    ) -> None:
        """Update file watcher when a session's file path changes."""
        if not self._session:
            return

        if old_path:
            # Remove old watcher
            self._watcher_manager.remove_callback(
                self._canonicalize_path(old_path), self._handle_file_change
            )

        if not session.app_file_manager.path:
            return

        # Attach new watcher
        self._watcher_manager.add_callback(
            self._canonicalize_path(session.app_file_manager.path),
            self._handle_file_change,
        )

        LOGGER.info(
            "Updated file watcher for session %s from %s to %s",
            session.initialization_id,
            old_path,
            session.app_file_manager.path,
        )
