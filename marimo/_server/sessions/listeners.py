# Copyright 2024 Marimo. All rights reserved.
"""Common session event listeners.

Provides reusable listeners for common session lifecycle concerns like
tracking recent files, managing caches, etc.
"""

from __future__ import annotations

from marimo._server.recents import RecentFilesManager
from marimo._server.sessions.events import SessionEventListener
from marimo._server.sessions.session import Session
from marimo._types.ids import SessionId


class RecentsTrackerListener(SessionEventListener):
    """Event listener that tracks recently accessed files."""

    def __init__(self, recents_manager: RecentFilesManager) -> None:
        """Initialize the recents tracker listener.

        Args:
            recents_manager: Manager for recent files
        """
        self._recents = recents_manager

    async def on_session_created(self, session: Session) -> None:
        """Update recent files when a session is created."""
        if session.app_file_manager.path:
            self._recents.touch(session.app_file_manager.path)

    async def on_session_closed(self, session: Session) -> None:
        """No action needed on session close."""
        pass

    async def on_session_resumed(
        self, session: Session, old_id: SessionId
    ) -> None:
        """Update recent files when a session is resumed."""
        del old_id
        if session.app_file_manager.path:
            self._recents.touch(session.app_file_manager.path)
