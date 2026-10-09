# Copyright 2026 Marimo. All rights reserved.
"""Live attachments for notebook handoffs."""

from __future__ import annotations

from typing import Literal

import msgspec

AttachmentKind = Literal["agent", "client"]


class Attachment(msgspec.Struct, frozen=True):
    """A connection to a notebook's handoff stream.

    Args:
        id (str): Identity supplied by the client or minted by the server.
        kind (AttachmentKind): Whether the connection receives handoffs.
        name (str | None): Human-readable label for the connection.
        since (float): Time of attachment in epoch seconds.
    """

    id: str
    kind: AttachmentKind
    name: str | None
    since: float
