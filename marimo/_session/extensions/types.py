# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from marimo._session.events import SessionEventBus
    from marimo._session.session import Session


class SessionExtension(Protocol):
    """Base class for session extensions.

    Extensions can hook into session lifecycle events and add
    functionality without modifying the core Session class.
    """

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        """Called when extension is attached to a session.

        Args:
            session: The session this extension is attached to
            event_bus: Event bus for subscribing to session events
        """
        ...

    def on_detach(self) -> None:
        """Called when extension is detached from session (cleanup)."""
        ...
