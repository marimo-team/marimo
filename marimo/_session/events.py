# Copyright 2026 Marimo. All rights reserved.
"""Event system for session lifecycle events.

Provides an event bus and listeners for session creation, closure, and resumption.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._messaging.types import KernelMessage
from marimo._types.ids import ConsumerId, SessionId

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

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
        return

    async def on_session_closed(self, session: Session) -> None:
        """Called when a session is closed."""
        del session
        return

    async def on_session_resumed(
        self, session: Session, old_id: SessionId
    ) -> None:
        """Called when a session is resumed with a new ID."""
        del session
        del old_id
        return

    async def on_session_notebook_renamed(
        self, session: Session, old_path: str | None
    ) -> None:
        """Called when a session notebook is renamed."""
        del session
        del old_path
        return

    def on_notification_sent(
        self, session: Session, notification: KernelMessage
    ) -> None:
        """Called when a notification is emitted by a session."""
        del session
        del notification
        return

    def on_received_command(
        self,
        session: Session,
        request: commands.CommandMessage,
        from_consumer_id: ConsumerId | None,
    ) -> None:
        """Called when a command is received."""
        del session
        del request
        del from_consumer_id
        return

    def on_received_stdin(self, session: Session, stdin: str) -> None:
        """Called when stdin is received."""
        del session
        del stdin
        return


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

    def _emit(
        self,
        event_name: str,
        call: Callable[[SessionEventListener], None],
    ) -> None:
        """Dispatch a synchronous event to all listeners."""
        for listener in list(self._listeners):
            try:
                call(listener)
            except Exception as e:
                LOGGER.error(
                    "Error handling %s for listener %s: %s",
                    event_name,
                    listener,
                    e,
                )

    async def _emit_async(
        self,
        event_name: str,
        call: Callable[[SessionEventListener], Awaitable[None]],
    ) -> None:
        """Dispatch an async event to all listeners."""
        for listener in list(self._listeners):
            try:
                await call(listener)
            except Exception as e:
                LOGGER.error(
                    "Error handling %s for listener %s: %s",
                    event_name,
                    listener,
                    e,
                )

    async def emit_session_created(self, session: Session) -> None:
        """Emit a session created event."""
        await self._emit_async(
            "session_created",
            lambda listener: listener.on_session_created(session),
        )

    async def emit_session_closed(self, session: Session) -> None:
        """Emit a session closed event."""
        await self._emit_async(
            "session_closed",
            lambda listener: listener.on_session_closed(session),
        )

    async def emit_session_resumed(
        self, session: Session, old_id: SessionId
    ) -> None:
        """Emit a session resumed event."""
        await self._emit_async(
            "session_resumed",
            lambda listener: listener.on_session_resumed(session, old_id),
        )

    async def emit_session_notebook_renamed(
        self, session: Session, old_path: str | None
    ) -> None:
        """Emit a session renamed event."""
        await self._emit_async(
            "session_notebook_renamed",
            lambda listener: listener.on_session_notebook_renamed(
                session, old_path
            ),
        )

    def emit_notification_sent(
        self, session: Session, notification: KernelMessage
    ) -> None:
        """Emit a notification sent event."""
        self._emit(
            "notification_sent",
            lambda listener: listener.on_notification_sent(
                session, notification
            ),
        )

    def emit_received_command(
        self,
        session: Session,
        request: commands.CommandMessage,
        from_consumer_id: ConsumerId | None,
    ) -> None:
        """Emit a received command event."""
        self._emit(
            "received_command",
            lambda listener: listener.on_received_command(
                session, request, from_consumer_id
            ),
        )

    def emit_received_stdin(self, session: Session, stdin: str) -> None:
        """Emit a received stdin event."""
        self._emit(
            "received_stdin",
            lambda listener: listener.on_received_stdin(session, stdin),
        )
