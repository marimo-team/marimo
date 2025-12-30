# Copyright 2026 Marimo. All rights reserved.
"""Utility functions for session management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from marimo._messaging.serde import serialize_kernel_message
from marimo._session.model import ConnectionState
from marimo._types.ids import ConsumerId

if TYPE_CHECKING:
    from marimo._messaging.notification import NotificationMessage
    from marimo._session.session import Session


def send_message_to_consumer(
    session: Session,
    operation: NotificationMessage,
    consumer_id: Optional[ConsumerId],
) -> None:
    """Send a message operation to a specific consumer in a session."""
    notification = serialize_kernel_message(operation)
    if session.connection_state() == ConnectionState.OPEN:
        for consumer, c_id in session.consumers.items():
            if c_id == consumer_id:
                consumer.notify(notification)
