# Copyright 2024 Marimo. All rights reserved.
"""Event system for session lifecycle events.

Provides an event bus and listeners for session creation, closure, and resumption.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._types.ids import SessionId

if TYPE_CHECKING:
    from marimo._server.sessions.session import Session

LOGGER = _loggers.marimo_logger()


class SessionEventListener:
    """Base class for session event listeners.

    Not all methods need to be implemented.
    """

    async def on_session_created(self, session: Session) -> None:
        """Called when a session is created."""
        del session
        return None

    async def on_session_closed(self, session: Session) -> None:
        """Called when a session is closed."""
        del session
        return None

    async def on_session_resumed(
        self, session: Session, old_id: SessionId
    ) -> None:
        """Called when a session is resumed with a new ID."""
        del session
        del old_id
        return None

    async def on_session_notebook_renamed(
        self, session: Session, new_path: str
    ) -> None:
        """Called when a session notebook is renamed."""
        del session
        del new_path
        return None


class SessionEventBus:
    """Event bus for coordinating session lifecycle events.

    Allows components to react to session events without tight coupling.
    """

    def __init__(self) -> None:
        self._listeners: list[SessionEventListener] = []

    def subscribe(self, listener: SessionEventListener) -> None:
        """Subscribe a listener to session events."""
        self._listeners.append(listener)

    def unsubscribe(self, listener: SessionEventListener) -> None:
        """Unsubscribe a listener from session events."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def emit_session_created(self, session: Session) -> None:
        """Emit a session created event."""
        for listener in self._listeners:
            try:
                await listener.on_session_created(session)
            except Exception as e:
                LOGGER.error(
                    "Error handling session created event for listener %s: %s",
                    listener,
                    e,
                )
                continue

    async def emit_session_closed(self, session: Session) -> None:
        """Emit a session closed event."""
        for listener in self._listeners:
            try:
                await listener.on_session_closed(session)
            except Exception as e:
                LOGGER.error(
                    "Error handling session closed event for listener %s: %s",
                    listener,
                    e,
                )
                continue

    async def emit_session_resumed(
        self, session: Session, old_id: SessionId
    ) -> None:
        """Emit a session resumed event."""
        for listener in self._listeners:
            try:
                await listener.on_session_resumed(session, old_id)
            except Exception as e:
                LOGGER.error(
                    "Error handling session resumed event for listener %s: %s",
                    listener,
                    e,
                )
                continue

    async def emit_session_notebook_renamed(
        self, session: Session, new_path: str
    ) -> None:
        """Emit a session renamed event."""
        for listener in self._listeners:
            try:
                await listener.on_session_notebook_renamed(session, new_path)
            except Exception as e:
                LOGGER.error(
                    "Error handling session notebook renamed event for listener %s: %s",
                    listener,
                    e,
                )
                continue
