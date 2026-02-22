# Copyright 2026 Marimo. All rights reserved.
"""File watcher integration for sessions.

Provides clean abstraction for attaching/detaching file watchers to sessions
without leaking implementation details or monkey-patching.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from marimo import _loggers
from marimo._messaging.notification import UpdateCssNotification
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


def _resolve_css_path(session: Session) -> Path | None:
    """Resolve the absolute path to the CSS file from session config."""
    css_file = session.app_file_manager.app.config.css_file
    notebook_path = session.app_file_manager.path
    if not css_file or not notebook_path:
        return None

    filepath = Path(css_file)
    if not filepath.is_absolute():
        filepath = Path(notebook_path).parent / filepath

    return filepath


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
        self._css_path: Path | None = None

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        """Attach the file watcher extension to a session."""
        self._event_bus = event_bus
        self._event_bus.subscribe(self)
        self._session = session

        if not session.app_file_manager.path:
            return

        # Register notebook file watcher
        self._watcher_manager.add_callback(
            Path(session.app_file_manager.path), self._handle_file_change
        )

        # Register CSS file watcher if configured
        self._start_css_watcher(session)

        LOGGER.info(
            "Attached file watcher for session %s at path %s",
            session.initialization_id,
            session.app_file_manager.path,
        )

    def _start_css_watcher(self, session: Session) -> None:
        """Start watching the CSS file if configured."""
        css_path = _resolve_css_path(session)
        if css_path and css_path.exists():
            self._css_path = css_path
            self._watcher_manager.add_callback(
                css_path, self._handle_css_change
            )
            LOGGER.debug("Watching CSS file: %s", css_path)

    def _stop_css_watcher(self) -> None:
        """Stop watching the current CSS file if any."""
        if self._css_path:
            self._watcher_manager.remove_callback(
                self._css_path, self._handle_css_change
            )
            LOGGER.debug("Stopped watching CSS file: %s", self._css_path)
            self._css_path = None

    def update_css_watcher(self, session: Session) -> None:
        """Update the CSS file watcher after a config change.

        Compares the currently watched path with the new config and
        registers/deregisters watchers as needed.
        """
        new_css_path = _resolve_css_path(session)

        # Nothing changed
        if self._css_path == new_css_path:
            return

        self._stop_css_watcher()
        if new_css_path and new_css_path.exists():
            self._css_path = new_css_path
            self._watcher_manager.add_callback(
                new_css_path, self._handle_css_change
            )
            LOGGER.debug("Updated CSS watcher to: %s", new_css_path)

    async def _handle_file_change(self, path: Path) -> None:
        """Handle a file change."""
        if not self._session:
            return

        await self._on_change_callback(path, self._session)

    async def _handle_css_change(self, path: Path) -> None:
        """Handle a CSS file change by pushing new content to the frontend."""
        if not self._session:
            return

        css_content = self._session.app_file_manager.read_css_file() or ""
        self._session.notify(
            UpdateCssNotification(css=css_content),
            from_consumer_id=None,
        )
        LOGGER.debug("Sent CSS update for: %s", path)

    def on_detach(self) -> None:
        """Detach the file watcher extension from a session."""
        if not self._session:
            return

        if not self._session.app_file_manager.path:
            return

        # Remove notebook file watcher
        self._watcher_manager.remove_callback(
            self._canonicalize_path(self._session.app_file_manager.path),
            self._handle_file_change,
        )

        # Remove CSS file watcher
        self._stop_css_watcher()

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
