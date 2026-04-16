# Copyright 2026 Marimo. All rights reserved.
"""Common session event listeners.

Provides reusable listeners for common session lifecycle concerns like
tracking recent files, managing caches, etc.
"""

from __future__ import annotations

from marimo._server.recents import RecentFilesManager
from marimo._session.extensions.types import EventAwareExtension
from marimo._session.session import Session
from marimo._types.ids import SessionId


class RecentsTrackerListener(EventAwareExtension):
    """Event listener that tracks recently accessed files."""

    def __init__(self, recents_manager: RecentFilesManager) -> None:
        """Initialize the recents tracker listener.

        Args:
            recents_manager: Manager for recent files
        """
        super().__init__()
        self._recents = recents_manager

    async def on_session_created(self, session: Session) -> None:
        """Update recent files when a session is created."""
        if session.app_file_manager.path:
            self._recents.touch(session.app_file_manager.path)

    async def on_session_closed(self, session: Session) -> None:
        """No action needed on session close."""

    async def on_session_resumed(
        self, session: Session, old_id: SessionId
    ) -> None:
        """Update recent files when a session is resumed."""
        del old_id
        if session.app_file_manager.path:
            self._recents.touch(session.app_file_manager.path)

    async def on_session_notebook_renamed(
        self, session: Session, old_path: str | None
    ) -> None:
        """Update recent files when a session notebook is renamed."""
        path = session.app_file_manager.path
        if not path:
            return
        if old_path:
            self._recents.rename(path, old_path)
        else:
            self._recents.touch(path)
