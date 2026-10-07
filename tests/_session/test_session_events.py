# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from marimo._ast.app import App, InternalApp
from marimo._config.manager import get_default_config_manager
from marimo._messaging.types import KernelMessage
from marimo._session.consumer import SessionConsumer
from marimo._session.events import SessionEventListener
from marimo._session.managers.kernel import KernelManagerImpl
from marimo._session.model import ConnectionState
from marimo._session.notebook import AppFileManager
from marimo._session.session import SessionImpl
from marimo._session.state.session_view import SessionView
from marimo._types.ids import ConsumerId, StableSessionId

if TYPE_CHECKING:
    from marimo._session.events import SessionEventBus
    from marimo._session.types import Session


class Consumer(SessionConsumer):
    def __init__(self, consumer_id: str) -> None:
        self._id = ConsumerId(consumer_id)

    @property
    def consumer_id(self) -> ConsumerId:
        return self._id

    def notify(self, notification: KernelMessage) -> None:
        del notification

    def connection_state(self) -> ConnectionState:
        return ConnectionState.OPEN

    def on_attach(self, session: Session, event_bus: SessionEventBus) -> None:
        del session, event_bus

    def on_detach(self) -> None:
        pass


class Recorder(SessionEventListener):
    def __init__(self) -> None:
        self.events: list[tuple[str, ConsumerId]] = []

    def on_consumer_connected(
        self, session: Session, consumer: SessionConsumer
    ) -> None:
        del session
        self.events.append(("connected", consumer.consumer_id))

    def on_consumer_disconnected(
        self, session: Session, consumer: SessionConsumer
    ) -> None:
        del session
        self.events.append(("disconnected", consumer.consumer_id))


def make_session() -> SessionImpl:
    return SessionImpl(
        stable_id=StableSessionId("sess-test"),
        session_view=SessionView(),
        initialization_id="notebook.py",
        session_consumer=None,
        kernel_manager=MagicMock(spec=KernelManagerImpl),
        app_file_manager=AppFileManager.from_app(InternalApp(App())),
        config_manager=get_default_config_manager(current_path=None),
        ttl_seconds=None,
        extensions=[],
    )


def test_consumers_joining_and_leaving_are_announced() -> None:
    session = make_session()
    recorder = Recorder()
    session.event_bus.subscribe(recorder)
    browser = Consumer("browser")
    agent = Consumer("agent")

    try:
        session.connect_consumer(browser, main=True)
        session.connect_consumer(agent, main=False)
        session.disconnect_consumer(agent)
        session.disconnect_consumer(browser)
    finally:
        session.close()

    assert recorder.events == [
        ("connected", ConsumerId("browser")),
        ("connected", ConsumerId("agent")),
        ("disconnected", ConsumerId("agent")),
        ("disconnected", ConsumerId("browser")),
    ]


def test_a_replaced_consumer_leaving_is_not_announced() -> None:
    session = make_session()
    recorder = Recorder()
    session.event_bus.subscribe(recorder)
    first = Consumer("tab")
    second = Consumer("tab")

    try:
        session.connect_consumer(first, main=True)
        # The room keeps the newer registration under the same id.
        session.room.add_consumer(second, main=False)
        session.disconnect_consumer(first)
        assert session.room.get_consumer(ConsumerId("tab")) is second
        assert recorder.events == [("connected", ConsumerId("tab"))]
    finally:
        session.close()


def test_closing_a_session_announces_its_consumers_leaving() -> None:
    session = make_session()
    recorder = Recorder()
    session.event_bus.subscribe(recorder)
    session.connect_consumer(Consumer("tab"), main=True)
    session.connect_consumer(Consumer("agent"), main=False)

    session.close()

    assert recorder.events[2:] == [
        ("disconnected", ConsumerId("tab")),
        ("disconnected", ConsumerId("agent")),
    ]
    assert session.room.get_consumer(ConsumerId("tab")) is None
