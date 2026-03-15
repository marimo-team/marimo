# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from marimo._session.events import SessionEventListener

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import TypeVar

    from marimo._session.events import SessionEventBus
    from marimo._session.session import Session

    _T = TypeVar("_T")

__all__ = [
    "EventAwareExtension",
    "ExtensionRegistry",
    "SessionExtension",
]


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


class EventAwareExtension(SessionEventListener):
    """Base class for extensions that react to session events.

    Auto-subscribes to the event bus on attach, auto-unsubscribes on detach.
    Subclass this and override the event handlers you care about.
    """

    def __init__(self) -> None:
        self._session: Session | None = None
        self._event_bus: SessionEventBus | None = None

    @property
    def session(self) -> Session:
        assert self._session is not None
        return self._session

    @property
    def event_bus(self) -> SessionEventBus:
        assert self._event_bus is not None
        return self._event_bus

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        self._session = session
        self._event_bus = event_bus
        event_bus.subscribe(self)

    def on_detach(self) -> None:
        if self._event_bus:
            self._event_bus.unsubscribe(self)
        self._event_bus = None
        self._session = None


class ExtensionRegistry:
    """Registry for session extensions with typed lookup."""

    def __init__(self) -> None:
        self._extensions: list[SessionExtension] = []

    def add(self, *extensions: SessionExtension) -> None:
        self._extensions.extend(extensions)

    def remove(self, extension: SessionExtension) -> None:
        if extension in self._extensions:
            self._extensions.remove(extension)

    def get(self, ext_type: type[_T]) -> _T | None:
        for ext in self._extensions:
            if isinstance(ext, ext_type):
                return ext  # type: ignore[return-value]
        return None

    def __iter__(self) -> Iterator[SessionExtension]:
        return iter(list(self._extensions))

    def __contains__(self, item: SessionExtension) -> bool:
        return item in self._extensions
