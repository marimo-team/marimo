# Copyright 2026 Marimo. All rights reserved.
"""Room management for broadcasting messages to multiple consumers.

A Room is a collection of SessionConsumers that can be used to broadcast
messages to all of them. Each room has one main consumer (the primary
session) and can have multiple kiosk consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class _ConsumerState:
    """A consumer in a room and its current capabilities.

    Capabilities are mutable: a takeover restamps them in place.
    """

    consumer: SessionConsumer
    capabilities: ConsumerCapabilities


class Room:
    """
    A room is a collection of SessionConsumers
    that can be used to broadcast messages to all
    of them.
    """

    def __init__(self) -> None:
        self.main_consumer: SessionConsumer | None = None
        self.consumers: dict[ConsumerId, _ConsumerState] = {}

    @property
    def size(self) -> int:
        return len(self.consumers)

    def add_consumer(
        self,
        consumer: SessionConsumer,
        *,
        # Whether the consumer is the main session consumer
        # We only allow one main consumer, the rest are kiosk consumers
        main: bool,
        capabilities: ConsumerCapabilities | None = None,
    ) -> None:
        if capabilities is None:
            # Non-main connections default to interactors (drive UI state, no
            # edit). Pure read-only is opt-in, passed explicitly by the caller.
            capabilities = ConsumerCapabilities(edit=main, interact=True)
        self.consumers[consumer.consumer_id] = _ConsumerState(
            consumer=consumer, capabilities=capabilities
        )
        if main:
            assert self.main_consumer is None, (
                "Main session consumer already exists"
            )
            self.main_consumer = consumer

    def remove_consumer(self, consumer: SessionConsumer) -> None:
        state = self.consumers.get(consumer.consumer_id)
        if state is None:
            LOGGER.debug(
                "Attempted to remove a consumer that was not in room."
            )
            return

        if state.consumer is not consumer:
            # A newer consumer re-registered under this id (reconnect or
            # takeover race). Tear down the stale socket but leave the live
            # registration intact.
            consumer.on_detach()
            return

        if consumer == self.main_consumer:
            self.main_consumer = None
        self.consumers.pop(consumer.consumer_id)
        consumer.on_detach()

    def promote_consumer_to_main(self, consumer: SessionConsumer) -> None:
        """Promote a consumer to be the main consumer of the room.

        Demotes the current main consumer (editor) to an interactor
        (`edit=False, interact=True`). Notifies each affected consumer of its
        capability change.
        """

        assert consumer.consumer_id in self.consumers, (
            "Consumer must be in the room to be promoted."
        )
        previous_main_consumer = self.main_consumer

        if previous_main_consumer is consumer:
            # The consumer is already the main consumer, no need to promote.
            return

        self.main_consumer = consumer

        if previous_main_consumer is not None:
            self.consumers[
                previous_main_consumer.consumer_id
            ].capabilities = ConsumerCapabilities(edit=False, interact=True)
            self._notify_consumer_capability_change(
                previous_main_consumer,
                self.get_capabilities(previous_main_consumer),
            )
        self.consumers[
            consumer.consumer_id
        ].capabilities = ConsumerCapabilities(edit=True, interact=True)
        self._notify_consumer_capability_change(
            consumer, self.get_capabilities(consumer)
        )

    def get_capabilities(
        self, consumer: SessionConsumer
    ) -> ConsumerCapabilities:
        """Get the stored capabilities of a consumer in this room."""
        state = self.consumers.get(consumer.consumer_id)
        if state is None:
            return ConsumerCapabilities(edit=False, interact=False)
        return state.capabilities

    def get_consumer(self, consumer_id: ConsumerId) -> SessionConsumer | None:
        state = self.consumers.get(consumer_id)
        return state.consumer if state is not None else None

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
        for state in self.consumers.values():
            consumer = state.consumer
            if consumer.consumer_id == except_consumer:
                continue
            if consumer.connection_state() == ConnectionState.OPEN:
                consumer.notify(notification)

    def close(self) -> None:
        # We don't need to detach consumers here because
        # they will be detached when the session is closed.
        self.consumers = {}
        self.main_consumer = None
