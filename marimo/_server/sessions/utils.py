# Copyright 2024 Marimo. All rights reserved.
"""Utility functions for session management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from marimo._server.model import ConnectionState
from marimo._types.ids import ConsumerId

if TYPE_CHECKING:
    from marimo._messaging.ops import MessageOperation
    from marimo._server.sessions.session import Session


def send_message_to_consumer(
    session: Session,
    operation: MessageOperation,
    consumer_id: Optional[ConsumerId],
) -> None:
    """Send a message operation to a specific consumer in a session."""
    if session.connection_state() == ConnectionState.OPEN:
        for consumer, c_id in session.consumers.items():
            if c_id == consumer_id:
                consumer.write_operation(operation)
