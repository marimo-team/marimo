# Copyright 2026 Marimo. All rights reserved.
"""Repository for session storage and retrieval."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

from marimo._session.model import ConnectionState
from marimo._session.session import Session
from marimo._types.ids import ConsumerId, SessionId

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._server.file_router import MarimoFileKey


class SessionRepository:
    """In-memory storage for sessions with thread-safe operations."""

    def __init__(self) -> None:
        self._sessions: dict[SessionId, Session] = {}
        # Reverse mapping from session to session ID
        self._session_to_id: dict[Session, SessionId] = {}
        self._lock = asyncio.Lock()

    async def add(self, session_id: SessionId, session: Session) -> None:
        """Add a session to the repository."""
        async with self._lock:
            self._sessions[session_id] = session
            self._session_to_id[session] = session_id

    def add_sync(self, session_id: SessionId, session: Session) -> None:
        """Add a session synchronously (use when not in async context)."""
        self._sessions[session_id] = session
        self._session_to_id[session] = session_id

    async def get(self, session_id: SessionId) -> Optional[Session]:
        """Get a session by its ID."""
        async with self._lock:
            return self._sessions.get(session_id)

    def get_sync(self, session_id: SessionId) -> Optional[Session]:
        """Get a session synchronously."""
        return self._sessions.get(session_id)

    def get_by_consumer_id(self, consumer_id: ConsumerId) -> Optional[Session]:
        """Find a session by consumer ID (for kiosk mode)."""
        for session in self._sessions.values():
            if consumer_id in session.consumers.values():
                return session
        return None

    def get_by_file_key(self, file_key: MarimoFileKey) -> Optional[Session]:
        """Get a session by file key."""
        import os

        for session in self._sessions.values():
            if (
                session.initialization_id == file_key
                or session.app_file_manager.path == os.path.abspath(file_key)
            ):
                return session
        return None

    def get_by_file_path(self, file_path: str) -> list[Session]:
        """Get all sessions associated with a file path."""
        import os

        abs_path = os.path.abspath(file_path)
        return [
            session
            for session in self._sessions.values()
            if session.app_file_manager.path == abs_path
        ]

    @property
    def sessions(self) -> Mapping[SessionId, Session]:
        """Get all sessions as a dict."""
        return dict(self._sessions)

    def get_all(self) -> list[Session]:
        """Get all sessions."""
        return list(self._sessions.values())

    def get_all_session_ids(self) -> list[SessionId]:
        """Get all session IDs."""
        return list(self._sessions.keys())

    def get_active_sessions(self) -> list[Session]:
        """Get all sessions with open connections."""
        return [
            session
            for session in self._sessions.values()
            if session.connection_state() == ConnectionState.OPEN
        ]

    async def remove(self, session_id: SessionId) -> Optional[Session]:
        """Remove and return a session."""
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session and session in self._session_to_id:
                del self._session_to_id[session]
            return session

    def remove_sync(self, session_id: SessionId) -> Optional[Session]:
        """Remove a session synchronously."""
        session = self._sessions.pop(session_id, None)
        if session and session in self._session_to_id:
            del self._session_to_id[session]
        return session

    def get_session_id(self, session: Session) -> Optional[SessionId]:
        """Get the session ID for a session object."""
        return self._session_to_id.get(session)

    async def update_session_id(
        self, old_id: SessionId, new_id: SessionId
    ) -> bool:
        """Update a session's ID (for resume operations)."""
        async with self._lock:
            if old_id not in self._sessions:
                return False

            session = self._sessions[old_id]
            self._sessions[new_id] = session
            self._session_to_id[session] = new_id

            # Only delete if IDs are different
            if new_id != old_id:
                del self._sessions[old_id]

            return True

    def update_session_id_sync(
        self, old_id: SessionId, new_id: SessionId
    ) -> bool:
        """Update a session's ID synchronously."""
        if old_id not in self._sessions:
            return False

        session = self._sessions[old_id]
        self._sessions[new_id] = session
        self._session_to_id[session] = new_id

        # Only delete if IDs are different
        if new_id != old_id:
            del self._sessions[old_id]

        return True

    async def clear(self) -> None:
        """Clear all sessions."""
        async with self._lock:
            self._sessions.clear()
            self._session_to_id.clear()

    def clear_sync(self) -> None:
        """Clear all sessions synchronously."""
        self._sessions.clear()
        self._session_to_id.clear()

    def __len__(self) -> int:
        """Get the number of sessions."""
        return len(self._sessions)
