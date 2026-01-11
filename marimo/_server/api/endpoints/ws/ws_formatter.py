# Copyright 2026 Marimo. All rights reserved.
"""WebSocket message formatting utilities.

This module handles the wire format for WebSocket transport:
wrapping serialized notification data with operation metadata.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._messaging.serde import serialize_kernel_message

if TYPE_CHECKING:
    from marimo._messaging.notification import NotificationMessage


def format_wire_message(op: str, data: bytes) -> str:
    """Format a serialized message for WebSocket transport.

    Wraps serialized notification data with operation metadata
    for the WebSocket wire protocol.

    Args:
        op: The operation name (e.g., "cell-op", "kernel-ready")
        data: The serialized notification data as bytes

    Returns:
        JSON string in wire format: {"op": "...", "data": ...}
    """
    return f'{{"op": "{op}", "data": {data.decode("utf-8")}}}'


def serialize_notification_for_websocket(
    notification: NotificationMessage,
) -> str:
    """Serialize and format a notification for WebSocket transport.

    Combines serialization and wire formatting into a single operation.
    Useful when you have a notification object and need the final wire format.

    Args:
        notification: The notification to serialize and format

    Returns:
        JSON string in wire format: {"op": "...", "data": ...}
    """
    serialized = serialize_kernel_message(notification)
    op = notification.name
    return format_wire_message(op, serialized)
