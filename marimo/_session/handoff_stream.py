# Copyright 2026 Marimo. All rights reserved.
"""Live fan-out of notebook handoffs to attached agents."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import msgspec

from marimo._messaging.attachments import Attachment
from marimo._messaging.msgspec_encoder import encode_json_str
from marimo._server.sse import format_sse_event

if TYPE_CHECKING:
    from collections.abc import Callable

MAX_PENDING_EVENTS = 64


def sse_event(name: str, data: object) -> bytes:
    """Encode one named SSE event with a JSON payload.

    Args:
        name (str): Event name.
        data (object): Payload encoded with marimo's JSON encoder.
    """
    return format_sse_event(encode_json_str(data), event=name).encode("utf-8")


@dataclass
class AttachmentHandle:
    """A connection and its outgoing SSE messages.

    Args:
        attachment (Attachment): Description of the connection.
        queue (asyncio.Queue[bytes | None]): Messages followed by `None` on closure.
    """

    attachment: Attachment
    queue: asyncio.Queue[bytes | None]


def _end_queue(handle: AttachmentHandle) -> None:
    # Pending handoffs have no delivery guarantee after a connection ends.
    while not handle.queue.empty():
        handle.queue.get_nowait()
    handle.queue.put_nowait(None)


class HandoffStream:
    """A Session's live attachments, with no retained handoff history."""

    def __init__(
        self,
        *,
        on_attachments_changed: Callable[[list[Attachment]], None],
    ) -> None:
        """Create a stream.

        Args:
            on_attachments_changed (Callable[[list[Attachment]], None]): Callback
                with the full attachment list after each change.
        """
        self._on_attachments_changed = on_attachments_changed
        self._handles: dict[str, AttachmentHandle] = {}
        self._closed = False

    def attach(self, attachment: Attachment) -> AttachmentHandle:
        """Open a connection and preserve its attachment time on replacement.

        Args:
            attachment (Attachment): Identity and metadata for the connection.
        """
        if self._closed:
            raise ValueError("Handoff stream is closed")

        previous = self._handles.get(attachment.id)
        if previous is not None:
            attachment = msgspec.structs.replace(
                attachment, since=previous.attachment.since
            )
            _end_queue(previous)

        handle = AttachmentHandle(
            attachment=attachment,
            queue=asyncio.Queue(maxsize=MAX_PENDING_EVENTS),
        )
        handle.queue.put_nowait(sse_event("attached", attachment))
        self._handles[attachment.id] = handle
        self._on_attachments_changed(self.attachments())
        return handle

    def _detach(self, attachment_id: str) -> None:
        """Remove an attachment and end its queue.

        Args:
            attachment_id (str): Identity of the attachment to remove.
        """
        handle = self._handles.pop(attachment_id, None)
        if handle is None:
            return
        _end_queue(handle)
        self._on_attachments_changed(self.attachments())

    def release(self, handle: AttachmentHandle) -> None:
        """Detach a handle without removing its replacement.

        Args:
            handle (AttachmentHandle): Connection to release.
        """
        if self._handles.get(handle.attachment.id) is handle:
            self._detach(handle.attachment.id)

    def attachments(self) -> list[Attachment]:
        """Return the full list of live attachments."""
        return [handle.attachment for handle in self._handles.values()]

    def publish(self, payload: object) -> None:
        """Send a handoff to every live agent without retaining history.

        Args:
            payload (object): Content encoded as JSON without a required schema.
        """
        event = sse_event("handoff", payload)
        for handle in list(self._handles.values()):
            if handle.attachment.kind == "agent":
                try:
                    handle.queue.put_nowait(event)
                except asyncio.QueueFull:
                    self.release(handle)

    def close(self) -> None:
        """End all queues and remove the live attachments."""
        if self._closed:
            return
        self._closed = True
        for handle in self._handles.values():
            _end_queue(handle)
        if self._handles:
            self._handles.clear()
            self._on_attachments_changed([])
