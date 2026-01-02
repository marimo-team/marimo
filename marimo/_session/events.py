# Copyright 2026 Marimo. All rights reserved.
"""Event system for session lifecycle events.

Provides an event bus and listeners for session creation, closure, and resumption.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from marimo import _loggers
from marimo._messaging.types import KernelMessage
from marimo._types.ids import ConsumerId, SessionId

if TYPE_CHECKING:
    from marimo._runtime import commands
    from marimo._session.session import Session

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
        self, session: Session, old_path: str | None
    ) -> None:
        """Called when a session notebook is renamed."""
        del session
        del old_path
        return None

    def on_notification_sent(
        self, session: Session, notification: KernelMessage
    ) -> None:
        """Called when a notification is emitted by a session."""
        del session
        del notification
        return None

    def on_received_command(
        self,
        session: Session,
        request: commands.CommandMessage,
        from_consumer_id: Optional[ConsumerId],
    ) -> None:
        """Called when a command is received."""
        del session
        del request
        del from_consumer_id
        return None

    def on_received_stdin(self, session: Session, stdin: str) -> None:
        """Called when stdin is received."""
        del session
        del stdin
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
        self, session: Session, old_path: str | None
    ) -> None:
        """Emit a session renamed event."""
        for listener in self._listeners:
            try:
                await listener.on_session_notebook_renamed(session, old_path)
            except Exception as e:
                LOGGER.error(
                    "Error handling session notebook renamed event for listener %s: %s",
                    listener,
                    e,
                )
                continue

    def emit_notification_sent(
        self, session: Session, notification: KernelMessage
    ) -> None:
        """Emit a notification sent event."""
        for listener in self._listeners:
            try:
                listener.on_notification_sent(session, notification)
            except Exception as e:
                LOGGER.error(
                    "Error handling notification sent event for listener %s: %s",
                    listener,
                    e,
                )
                continue

    def emit_received_command(
        self,
        session: Session,
        request: commands.CommandMessage,
        from_consumer_id: Optional[ConsumerId],
    ) -> None:
        """Emit a received command event."""
        for listener in self._listeners:
            try:
                listener.on_received_command(
                    session, request, from_consumer_id
                )
            except Exception as e:
                LOGGER.error(
                    "Error handling received command event for listener %s: %s",
                    listener,
                    e,
                )
                continue

    def emit_received_stdin(self, session: Session, stdin: str) -> None:
        """Emit a received stdin event."""
        for listener in self._listeners:
            try:
                listener.on_received_stdin(session, stdin)
            except Exception as e:
                LOGGER.error(
                    "Error handling received stdin event for listener %s: %s",
                    listener,
                    e,
                )
                continue
