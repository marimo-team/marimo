# Copyright 2026 Marimo. All rights reserved.
"""Room management for broadcasting messages to multiple consumers.

A Room is a collection of SessionConsumers that can be used to broadcast
messages to all of them. Each room has one main consumer (the primary
session) and can have multiple kiosk consumers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._messaging.notification import (
    ConsumerCapabilities,
    ConsumerCapabilitiesNotification,
)
from marimo._messaging.serde import serialize_kernel_message
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
        self.main_consumer: SessionConsumer | None = None
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

    def promote_consumer_to_main(self, consumer: SessionConsumer) -> None:
        """Promote a consumer to be the main consumer of the room.

        Demotes the current main consumer (editor) to a regular consumer (reader).
        Emits a targeted notification to each targeted consumer to inform capability change.
        """

        assert consumer in self.consumers, (
            "Consumer must be in the room to be promoted."
        )
        previous_main_consumer = self.main_consumer

        if previous_main_consumer is consumer:
            # The consumer is already the main consumer, no need to promote.
            return

        self.main_consumer = consumer

        if previous_main_consumer is not None:
            self._notify_consumer_capability_change(
                previous_main_consumer,
                self.get_capabilities(previous_main_consumer),
            )
        self._notify_consumer_capability_change(
            consumer, self.get_capabilities(consumer)
        )

    def get_capabilities(
        self, consumer: SessionConsumer
    ) -> ConsumerCapabilities:
        """Get the capabilities of a consumer based on its role in the room."""
        is_editor = consumer is self.main_consumer
        return ConsumerCapabilities(edit=is_editor, interact=is_editor)

    def get_consumer(self, consumer_id: ConsumerId) -> SessionConsumer | None:
        for consumer, cid in self.consumers.items():
            if cid == consumer_id:
                return consumer
        return None

    def _notify_consumer_capability_change(
        self, consumer: SessionConsumer, capabilities: ConsumerCapabilities
    ) -> None:
        if consumer.connection_state() != ConnectionState.OPEN:
            return
        notification = ConsumerCapabilitiesNotification(
            consumer_capabilities=capabilities
        )
        consumer.notify(serialize_kernel_message(notification))

    def broadcast(
        self,
        notification: KernelMessage,
        *,
        except_consumer: ConsumerId | None,
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
