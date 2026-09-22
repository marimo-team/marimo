# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import queue
import threading
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from marimo._ast.app import App, InternalApp
from marimo._config.manager import get_default_config_manager
from marimo._messaging.notification import (
    InstallingPackageAlertNotification,
    OperationRunning,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._messaging.types import KernelMessage
from marimo._session.consumer import SessionConsumer
from marimo._session.extensions.extensions import (
    NotificationListenerExtension,
    SessionViewExtension,
)
from marimo._session.managers import KernelManagerImpl
from marimo._session.model import ConnectionState
from marimo._session.notebook import AppFileManager
from marimo._session.session import SessionImpl
from marimo._session.state.environment import (
    EnvironmentOperation,
    EnvironmentState,
)
from marimo._types.ids import ConsumerId
from marimo._utils.distributor import QueueDistributor

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def session_and_consumer() -> Iterator[tuple[SessionImpl, Mock]]:
    consumer = Mock(spec=SessionConsumer)
    consumer.consumer_id = ConsumerId("main")
    consumer.connection_state.return_value = ConnectionState.OPEN
    session = SessionImpl(
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


def _progress(log: str) -> InstallingPackageAlertNotification:
    return InstallingPackageAlertNotification(
        operation_id="install",
        status=OperationRunning(),
        packages={"numpy": "installing"},
        logs={"numpy": log},
        log_status="append",
    )


def _state(log: str) -> EnvironmentState:
    return EnvironmentState(
        restart_required=False,
        operations=[
            EnvironmentOperation(
                operation_id="install",
                status=OperationRunning(),
                packages={"numpy": "installing"},
                logs={"numpy": log},
                source="kernel",
            )
        ],
    )


@pytest.mark.parametrize("serialized", [False, True])
def test_notification_is_retained_before_consumer_receives_it(
    session_and_consumer: tuple[SessionImpl, Mock], serialized: bool
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
        serialize_kernel_message(progress) if serialized else progress,
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
    assert isinstance(distributor, QueueDistributor)
    try:
        messages.put(serialize_kernel_message(_progress("Downloading\n")))
        messages.put(serialize_kernel_message(_progress("Installing\n")))
        await asyncio.wait_for(delivered.wait(), timeout=5)
    finally:
        listener.on_detach()
        assert distributor.thread is not None
        await asyncio.to_thread(distributor.thread.join, 5)

    assert observed == [
        (loop_thread, _state("Downloading\n")),
        (loop_thread, _state("Downloading\nInstalling\n")),
    ]
