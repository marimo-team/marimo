# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import TYPE_CHECKING

from marimo._messaging.notification import NotificationMessage
from marimo._messaging.serde import serialize_kernel_message
from marimo._session.state.session_view import SessionView

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._session.consumer import SessionConsumer


class SessionStartup:
    """Retain startup progress independently of the connections observing it."""

    def __init__(self) -> None:
        self.view = SessionView()
        self._consumers: list[SessionConsumer] = []
        # Producers may report from worker threads. The view and consumer
        # queues belong to the loop that owns this startup.
        try:
            self._loop: asyncio.AbstractEventLoop | None = (
                asyncio.get_running_loop()
            )
        except RuntimeError:
            self._loop = None

    def notify(self, notification: NotificationMessage) -> None:
        if self._loop is not None and not self._on_loop():
            try:
                self._loop.call_soon_threadsafe(self.notify, notification)
            except RuntimeError:
                # Loop teardown can race with a worker's final output.
                if not self._loop.is_closed():
                    raise
            return
        self.view.add_notification(notification)
        message = serialize_kernel_message(notification)
        for consumer in self._consumers:
            consumer.notify(message)

    def _on_loop(self) -> bool:
        try:
            return asyncio.get_running_loop() is self._loop
        except RuntimeError:
            return False

    @contextmanager
    def subscribe(self, consumer: SessionConsumer) -> Iterator[None]:
        self._consumers.append(consumer)
        try:
            if self.view.startup_progress is not None:
                consumer.notify(
                    serialize_kernel_message(self.view.startup_progress)
                )
            yield
        finally:
            self._consumers.remove(consumer)
