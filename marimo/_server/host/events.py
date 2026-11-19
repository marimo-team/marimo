# Copyright 2026 Marimo. All rights reserved.
"""Internal marimo events for the host stream."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from marimo._core import protocol
from marimo._core.stream import ExtensionEvent, RoutedEvent, event_name
from marimo._messaging.cell_output import CellChannel
from marimo._messaging.notification import (
    CallbackOutputNotification,
    CellNotification,
    EditorNotification,
    ExecutionNotification,
    NotificationMessage,
    PdbInputNotification,
    PdbOutputNotification,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


class MarimoMessage(msgspec.Struct, frozen=True):
    """A marimo notification carried by the host event stream.

    This type is internal to marimo and may change between releases.
    """

    marimo: EditorNotification


class MarimoEvent(ExtensionEvent, frozen=True, tag="marimo"):
    """A typed envelope for internal marimo notifications."""

    data: MarimoMessage


def editor_events(
    notebook_id: protocol.NotebookId | None,
    notification: NotificationMessage,
    types: set[str] | None,
) -> Iterator[RoutedEvent]:
    if isinstance(notification, CallbackOutputNotification):
        # The legacy editor appends a single entry and replaces on a list.
        for entry in notification.entries:
            cell = CellNotification(
                cell_id=notification.cell_id, console=entry
            )
            yield RoutedEvent(
                MarimoEvent(MarimoMessage(cell)), notebook_id=notebook_id
            )
        return
    event = notification_event(
        notebook_id, notification, editor_session=True, types=types
    )
    if event is not None:
        yield event


def notification_event(
    notebook_id: protocol.NotebookId | None,
    notification: NotificationMessage,
    *,
    editor_session: bool = False,
    types: set[str] | None = None,
) -> RoutedEvent | None:
    """Project a kernel notification onto the host or attached editor stream."""
    if isinstance(
        notification, (ExecutionNotification, CallbackOutputNotification)
    ):
        return None
    # Attached editors still consume legacy cell updates (MO-8407) and handle
    # debugger commands for failed cells. Both use the editor session stream.
    if not editor_session and isinstance(
        notification,
        (CellNotification, PdbInputNotification, PdbOutputNotification),
    ):
        return None
    if (
        isinstance(notification, CellNotification)
        and types is not None
        and "execution" in types
        and notification.run_id is not None
        and notification.execution_id is not None
        and notification.output is not None
        and notification.output.channel == CellChannel.OUTPUT
    ):
        # The execution carries this value, including updates after completion.
        if (
            notification.status is None
            and notification.console is None
            and notification.serialization is msgspec.UNSET
        ):
            return None
        notification = msgspec.structs.replace(notification, output=None)
    run_id = getattr(notification, "run_id", None)
    return RoutedEvent(
        MarimoEvent(MarimoMessage(notification)),
        notebook_id=notebook_id,
        run_id=protocol.RunId(run_id) if run_id is not None else None,
    )


def _visible_event(
    event: RoutedEvent, *, include_code: bool
) -> protocol.Event | ExtensionEvent:
    """Encode a frame using this connection's source-visibility policy.

    Project a copy at delivery, so the host retains source and revisions for
    snapshots, replay, and staleness checks regardless of the reader.
    """
    message = event.event
    if not include_code and isinstance(message, protocol.CellEvent):
        cell = msgspec.structs.replace(message.data.cell, code=None)
        data = msgspec.structs.replace(message.data, cell=cell)
        message = msgspec.structs.replace(message, data=data)
    return message


def serialize_event(event: RoutedEvent, *, include_code: bool = True) -> str:
    """Encode a host WebSocket envelope."""
    return msgspec.json.encode(
        _visible_event(event, include_code=include_code)
    ).decode()


def serialize_sse_event(
    event: RoutedEvent, *, include_code: bool = True
) -> str:
    """Encode the same host event using SSE fields."""
    message = _visible_event(event, include_code=include_code)
    lines = []
    if message.id is not msgspec.UNSET:
        lines.append(f"id: {message.id}")
    lines.append(f"event: {event_name(message)}")
    lines.append(f"data: {msgspec.json.encode(message.data).decode()}")
    return "\n".join(lines) + "\n\n"
