# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import queue
import threading
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock

import pytest

from marimo._ast.app import App, InternalApp
from marimo._config.manager import get_default_config_manager
from marimo._messaging.notification import (
    EnvironmentOperation,
    EnvironmentOperationNotification,
    EnvironmentState,
    EnvironmentStateNotification,
    OperationRunning,
)
from marimo._messaging.serde import (
    deserialize_kernel_message,
    serialize_kernel_message,
)
from marimo._messaging.types import KernelMessage
from marimo._server.api.endpoints.ws.ws_connection_validator import (
    ConnectionParams,
)
from marimo._server.api.endpoints.ws_endpoint import WebSocketHandler
from marimo._session.consumer import SessionConsumer
from marimo._session.extensions.extensions import (
    NotificationListenerExtension,
    SessionViewExtension,
)
from marimo._session.managers import KernelManagerImpl
from marimo._session.model import ConnectionState, SessionMode
from marimo._session.notebook import AppFileManager
from marimo._session.session import SessionImpl
from marimo._session.state.session_view import SessionView
from marimo._types.ids import ConsumerId, SessionId
from marimo._utils.distributor import QueueDistributor

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def session_and_consumer() -> Iterator[tuple[SessionImpl, Mock]]:
    consumer = Mock(spec=SessionConsumer)
    consumer.consumer_id = ConsumerId("main")
    consumer.connection_state.return_value = ConnectionState.OPEN
    session = SessionImpl(
        session_view=SessionView(),
        initialization_id="notebook.py",
        session_consumer=consumer,
        kernel_manager=Mock(spec=KernelManagerImpl),
        app_file_manager=AppFileManager.from_app(InternalApp(App())),
        config_manager=get_default_config_manager(current_path=None),
        ttl_seconds=None,
        extensions=[SessionViewExtension()],
    )
    try:
        yield session, consumer
    finally:
        session.close()


def _progress(log: str) -> EnvironmentOperationNotification:
    return EnvironmentOperationNotification(
        action="install",
        source="kernel",
        operation_id="install",
        status=OperationRunning(),
        packages={"numpy": "running"},
        logs={"numpy": log},
        log_mode="append",
    )


def _state(log: str) -> EnvironmentState:
    return EnvironmentState(
        restart_required=False,
        operations=[
            EnvironmentOperation(
                action="install",
                operation_id="install",
                status=OperationRunning(),
                packages={"numpy": "running"},
                logs={"numpy": log},
                source="kernel",
            )
        ],
    )


def test_notification_is_retained_before_consumer_receives_it(
    session_and_consumer: tuple[SessionImpl, Mock],
) -> None:
    session, consumer = session_and_consumer
    observed: list[EnvironmentState] = []

    def receive(_message: KernelMessage) -> None:
        observed.append(
            session.get_current_state().get_environment_state("kernel")
        )

    consumer.notify.side_effect = receive
    progress = _progress("Downloading\n")
    session.notify(
        progress,
        from_consumer_id=None,
    )

    assert observed == [_state("Downloading\n")]


async def test_queued_kernel_messages_update_and_deliver_on_session_loop(
    session_and_consumer: tuple[SessionImpl, Mock],
) -> None:
    session, consumer = session_and_consumer
    loop = asyncio.get_running_loop()
    loop_thread = threading.get_ident()
    delivered = asyncio.Event()
    observed: list[tuple[int, EnvironmentState]] = []

    def receive(_message: KernelMessage) -> None:
        observed.append(
            (
                threading.get_ident(),
                session.get_current_state().get_environment_state("kernel"),
            )
        )
        if len(observed) == 2:
            loop.call_soon_threadsafe(delivered.set)

    consumer.notify.side_effect = receive
    messages: queue.Queue[KernelMessage | None] = queue.Queue()
    queue_manager = Mock(stream_queue=messages)
    listener = NotificationListenerExtension(Mock(), queue_manager)
    listener.on_attach(session, session._event_bus)
    distributor = listener.distributor
    try:
        assert isinstance(distributor, QueueDistributor)
        messages.put(serialize_kernel_message(_progress("Downloading\n")))
        messages.put(serialize_kernel_message(_progress("Installing\n")))
        await asyncio.wait_for(delivered.wait(), timeout=5)
    finally:
        listener.on_detach()
        if (
            isinstance(distributor, QueueDistributor)
            and distributor.thread is not None
        ):
            await asyncio.to_thread(distributor.thread.join, 5)

    assert observed == [
        (loop_thread, _state("Downloading\n")),
        (loop_thread, _state("Downloading\nInstalling\n")),
    ]


async def test_reconnect_snapshot_precedes_a_queued_live_update(
    session_and_consumer: tuple[SessionImpl, Mock],
) -> None:
    session, consumer = session_and_consumer
    session.disconnect_consumer(consumer)
    session.notify(_progress("Before\n"), from_consumer_id=None)
    handler = WebSocketHandler(
        websocket=MagicMock(),
        manager=MagicMock(),
        params=ConnectionParams(
            session_id=SessionId("reconnected"),
            file_key="notebook.py",
            kiosk=False,
            auto_instantiate=False,
            rtc_enabled=False,
        ),
        mode=SessionMode.EDIT,
    )
    asyncio.get_running_loop().call_soon(
        lambda: session.notify(_progress("After\n"), from_consumer_id=None)
    )
    handler._reconnect_session(session, replay=False)
    await asyncio.sleep(0)

    messages = []
    while not handler.message_queue.empty():
        messages.append(
            deserialize_kernel_message(handler.message_queue.get_nowait())
        )
    assert [
        message
        for message in messages
        if isinstance(
            message,
            (EnvironmentStateNotification, EnvironmentOperationNotification),
        )
    ] == [
        EnvironmentStateNotification(
            source="kernel", state=_state("Before\n")
        ),
        EnvironmentStateNotification(
            source="server",
            state=EnvironmentState(restart_required=False, operations=[]),
        ),
        _progress("After\n"),
    ]


def test_queue_can_be_reused_after_its_listener_loop_closes(
    session_and_consumer: tuple[SessionImpl, Mock],
) -> None:
    session, consumer = session_and_consumer
    messages: queue.Queue[KernelMessage | None] = queue.Queue()
    listener = NotificationListenerExtension(
        Mock(), Mock(stream_queue=messages)
    )
    loop = asyncio.new_event_loop()

    async def attach() -> QueueDistributor[KernelMessage]:
        listener.on_attach(session, session._event_bus)
        assert isinstance(listener.distributor, QueueDistributor)
        return listener.distributor

    distributor = loop.run_until_complete(attach())
    loop.close()
    try:
        messages.put(serialize_kernel_message(_progress("Late output\n")))
        # Queue the sentinel after the late message, before detaching, to
        # exercise a callback racing with loop teardown.
        distributor.stop()
        assert distributor.thread is not None
        distributor.thread.join(5)
        assert not distributor.thread.is_alive()
        assert messages.empty()
        consumer.notify.assert_not_called()
    finally:
        listener.on_detach()
