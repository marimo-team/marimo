# Copyright 2026 Marimo. All rights reserved.
"""Internal marimo events for the host stream."""

from __future__ import annotations

import msgspec

from marimo._core import protocol
from marimo._core.stream import ExtensionEvent, RoutedEvent, event_name
from marimo._messaging.notification import NotificationMessage


class MarimoMessage(msgspec.Struct, frozen=True):
    """A marimo notification carried by the host event stream.

    This type is internal to marimo and may change between releases.
    """

    marimo: NotificationMessage


class MarimoEvent(ExtensionEvent, frozen=True, tag="marimo"):
    """A typed envelope for internal marimo notifications."""

    data: MarimoMessage


def notification_event(
    notebook_id: protocol.NotebookId, notification: NotificationMessage
) -> RoutedEvent:
    """Wrap a notification with its notebook and optional run scope."""
    run_id = getattr(notification, "run_id", None)
    return RoutedEvent(
        MarimoEvent(MarimoMessage(notification)),
        notebook_id=notebook_id,
        run_id=protocol.RunId(run_id) if run_id is not None else None,
    )


def serialize_event(event: RoutedEvent) -> str:
    """Encode one host event as a WebSocket frame."""
    return msgspec.json.encode(event.event).decode()


def serialize_sse_event(event: RoutedEvent) -> str:
    """Encode a host event using SSE fields."""
    message = event.event
    lines = []
    if message.id is not msgspec.UNSET:
        lines.append(f"id: {message.id}")
    lines.append(f"event: {event_name(message)}")
    lines.append(f"data: {msgspec.json.encode(message.data).decode()}")
    return "\n".join(lines) + "\n\n"
