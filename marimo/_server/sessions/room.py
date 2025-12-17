# Copyright 2024 Marimo. All rights reserved.
"""Room management for broadcasting messages to multiple consumers.

A Room is a collection of SessionConsumers that can be used to broadcast
messages to all of them. Each room has one main consumer (the primary
session) and can have multiple kiosk consumers.
"""

from __future__ import annotations

from typing import Optional

from marimo import _loggers
from marimo._messaging.ops import MessageOperation
from marimo._server.model import ConnectionState, SessionConsumer
from marimo._types.ids import ConsumerId
from marimo._utils.disposable import Disposable

LOGGER = _loggers.marimo_logger()


class Room:
    """
    A room is a collection of SessionConsumers
    that can be used to broadcast messages to all
    of them.
    """

    def __init__(self) -> None:
        self.main_consumer: Optional[SessionConsumer] = None
        self.consumers: dict[SessionConsumer, ConsumerId] = {}
        self.disposables: dict[SessionConsumer, Disposable] = {}

    @property
    def size(self) -> int:
        return len(self.consumers)

    def add_consumer(
        self,
        consumer: SessionConsumer,
        dispose: Disposable,
        consumer_id: ConsumerId,
        # Whether the consumer is the main session consumer
        # We only allow one main consumer, the rest are kiosk consumers
        main: bool,
    ) -> None:
        self.consumers[consumer] = consumer_id
        self.disposables[consumer] = dispose
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
        disposable = self.disposables.pop(consumer)
        try:
            consumer.on_stop()
        finally:
            disposable.dispose()

    def broadcast(
        self,
        operation: MessageOperation,
        except_consumer: Optional[ConsumerId],
    ) -> None:
        for consumer in self.consumers:
            if consumer.consumer_id == except_consumer:
                continue
            if consumer.connection_state() == ConnectionState.OPEN:
                consumer.write_operation(operation)

    def close(self) -> None:
        for consumer in self.consumers:
            disposable = self.disposables.pop(consumer)
            consumer.on_stop()
            disposable.dispose()
        self.consumers = {}
        self.main_consumer = None
