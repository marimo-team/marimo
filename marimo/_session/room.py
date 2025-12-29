# Copyright 2026 Marimo. All rights reserved.
"""Room management for broadcasting messages to multiple consumers.

A Room is a collection of SessionConsumers that can be used to broadcast
messages to all of them. Each room has one main consumer (the primary
session) and can have multiple kiosk consumers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from marimo import _loggers
from marimo._messaging.types import KernelMessage
from marimo._session.model import ConnectionState
from marimo._types.ids import ConsumerId

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from marimo._session.consumer import SessionConsumer


class Room:
    """
    A room is a collection of SessionConsumers
    that can be used to broadcast messages to all
    of them.
    """

    def __init__(self) -> None:
        self.main_consumer: Optional[SessionConsumer] = None
        self.consumers: dict[SessionConsumer, ConsumerId] = {}

    @property
    def size(self) -> int:
        return len(self.consumers)

    def add_consumer(
        self,
        consumer: SessionConsumer,
        *,
        consumer_id: ConsumerId,
        # Whether the consumer is the main session consumer
        # We only allow one main consumer, the rest are kiosk consumers
        main: bool,
    ) -> None:
        self.consumers[consumer] = consumer_id
        if main:
            assert self.main_consumer is None, (
                "Main session consumer already exists"
            )
            self.main_consumer = consumer

    def remove_consumer(self, consumer: SessionConsumer) -> None:
        if consumer not in self.consumers:
            LOGGER.debug(
                "Attempted to remove a consumer that was not in room."
            )
            return

        if consumer == self.main_consumer:
            self.main_consumer = None
        self.consumers.pop(consumer)
        consumer.on_detach()

    def broadcast(
        self,
        notification: KernelMessage,
        *,
        except_consumer: Optional[ConsumerId],
    ) -> None:
        """Broadcast a notification to all consumers except the one specified."""
        for consumer in self.consumers:
            if consumer.consumer_id == except_consumer:
                continue
            if consumer.connection_state() == ConnectionState.OPEN:
                consumer.notify(notification)

    def close(self) -> None:
        # We don't need to detach consumers here because
        # they will be detached when the session is closed.
        self.consumers = {}
        self.main_consumer = None
