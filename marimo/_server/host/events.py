# Copyright 2026 Marimo. All rights reserved.
"""Internal marimo events for the host stream."""

from __future__ import annotations

import msgspec

from marimo._core import protocol
from marimo._core.stream import Event
from marimo._messaging.notification import NotificationMessage


class MarimoMessage(msgspec.Struct, frozen=True):
    """A marimo notification carried by the host event stream.

    This type is internal to marimo and may change between releases.
    """

    marimo: NotificationMessage


def notification_event(
    notebook_id: protocol.NotebookId, notification: NotificationMessage
) -> Event:
    """Wrap a notification with its notebook and optional run scope."""
    run_id = getattr(notification, "run_id", None)
    return Event(
        "marimo",
        MarimoMessage(notification),
        notebook_id=notebook_id,
        run_id=protocol.RunId(run_id) if run_id is not None else None,
    )
