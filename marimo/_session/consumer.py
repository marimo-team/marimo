# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from marimo._session.extensions.types import SessionExtension
from marimo._types.ids import ConsumerId

if TYPE_CHECKING:
    from marimo._messaging.types import KernelMessage
    from marimo._session.events import SessionEventBus
    from marimo._session.model import ConnectionState
    from marimo._session.types import Session


class SessionConsumer(ABC, SessionExtension):
    """
    Consumer for a session. This extends the SessionExtension interface.

    This allows us to communicate with a session via different
    connection types.
    """

    @property
    @abstractmethod
    def consumer_id(self) -> ConsumerId: ...

    @abstractmethod
    def notify(self, notification: KernelMessage) -> None: ...

    @abstractmethod
    def connection_state(self) -> ConnectionState: ...


class NoOpSessionConsumer(SessionConsumer):
    """Minimal session consumer that ignores all notifications.

    Useful for headless/MCP-managed sessions that don't need to
    push kernel messages to a frontend.
    """

    def __init__(self, consumer_id: str) -> None:
        self._consumer_id = ConsumerId(consumer_id)

    @property
    def consumer_id(self) -> ConsumerId:
        return self._consumer_id

    def notify(self, notification: KernelMessage) -> None:
        pass

    def connection_state(self) -> ConnectionState:
        from marimo._session.model import ConnectionState

        return ConnectionState.OPEN

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        pass

    def on_detach(self) -> None:
        pass
