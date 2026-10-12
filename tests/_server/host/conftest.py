# Copyright 2026 Marimo. All rights reserved.
"""Session fakes for host backend tests."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from marimo._core import backend as be
from marimo._messaging.notification import NotificationMessage
from marimo._messaging.notebook import NotebookDocument
from marimo._messaging.serde import serialize_kernel_message
from marimo._session.consumer import SessionConsumer
from marimo._session.events import SessionEventBus
from marimo._session.model import ConnectionState
from marimo._session.types import KernelState
from marimo._types.ids import ConsumerId


class FakeSession:
    """A session fake with a real scratchpad lock and event bus."""

    def __init__(self, path: str | None = "/ws/forecasts.py") -> None:
        self.scratchpad_lock = asyncio.Lock()
        self.event_bus = SessionEventBus()
        self.consumers: list[tuple[SessionConsumer, bool]] = []
        self.commands: list[Any] = []
        self.notifications: list[NotificationMessage] = []
        self.submitted = asyncio.Event()
        self.interrupts = 0
        self.closed = False
        self.state = KernelState.RUNNING
        self.exit_info: Any = None
        self.app_file_manager = MagicMock()
        self.app_file_manager.path = path
        self.app_file_manager.app.config.asdict_difference.return_value = {}
        self.document = NotebookDocument([])
        self.session_view = MagicMock()
        self.config_manager = MagicMock()
        self.config_manager.get_config.return_value = {
            "runtime": {"on_cell_change": "autorun"}
        }

    def connect_consumer(
        self, consumer: SessionConsumer, *, main: bool
    ) -> None:
        self.consumers.append((consumer, main))
        consumer.on_attach(self, self.event_bus)  # type: ignore[arg-type]

    def disconnect_consumer(self, consumer: SessionConsumer) -> None:
        for entry in self.consumers:
            if entry[0] is consumer:
                self.consumers.remove(entry)
                consumer.on_detach()
                return

    def instantiate(self, request: Any, *, http_request: Any) -> None:
        del request, http_request

    def put_control_request(self, request: Any, from_consumer_id: Any) -> None:
        del from_consumer_id
        self.commands.append(request)
        self.submitted.set()

    def try_interrupt(self) -> None:
        self.interrupts += 1

    def kernel_state(self) -> KernelState:
        return self.state

    def kernel_exit_info(self) -> Any:
        return self.exit_info

    def connection_state(self) -> ConnectionState:
        return ConnectionState.OPEN

    def close(self, *, graceful: bool = False) -> None:
        del graceful
        self.closed = True
        for consumer, _ in self.consumers:
            consumer.on_detach()
        self.consumers.clear()

    def broadcast(self, notification: Any) -> None:
        """Send a notification to every consumer."""
        message = serialize_kernel_message(notification)
        for consumer, _ in list(self.consumers):
            consumer.notify(message)

    def notify(
        self,
        notification: NotificationMessage,
        from_consumer_id: ConsumerId | None = None,
    ) -> None:
        """What a session does with a notification: record and broadcast."""
        del from_consumer_id
        self.notifications.append(notification)
        self.broadcast(notification)


class FakeManager:
    """A session manager with configurable startup results and timing."""

    def __init__(self) -> None:
        self.sessions: dict[str, FakeSession] = {}
        self.event_bus = SessionEventBus()
        self.workspace: Any = MagicMock()
        self.starts: list[dict[str, Any]] = []
        self.next_session: Any = FakeSession()
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.release.set()

    async def create_session(
        self,
        session_id: str,
        session_consumer: SessionConsumer,
        query_params: Any,
        file_key: str,
        auto_instantiate: bool,
        *,
        main: bool = True,
    ) -> FakeSession:
        del query_params
        self.starts.append(
            {
                "file_key": file_key,
                "auto_instantiate": auto_instantiate,
                "main": main,
            }
        )
        self.started.set()
        await self.release.wait()
        if isinstance(self.next_session, Exception):
            raise self.next_session
        session: FakeSession = self.next_session
        self.sessions[session_id] = session
        session.connect_consumer(session_consumer, main=main)
        return session

    def close_session(self, session_id: str) -> bool:
        session = self.sessions.pop(session_id, None)
        if session is None:
            return False
        session.close()
        return True


class Observed:
    """Collects the messages a backend reports."""

    def __init__(self) -> None:
        self.messages: list[be.Message] = []
        self.changed = asyncio.Event()

    def __call__(self, message: be.Message) -> None:
        self.messages.append(message)
        self.changed.set()

    async def wait_for(self, kind: type[be.Message]) -> None:
        while not any(isinstance(message, kind) for message in self.messages):
            self.changed.clear()
            await asyncio.wait_for(self.changed.wait(), 5)

    def kinds(self) -> list[str]:
        return [type(m).__name__ for m in self.messages]


@pytest.fixture
def manager() -> FakeManager:
    return FakeManager()


@pytest.fixture
def observed() -> Observed:
    return Observed()
