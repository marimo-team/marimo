# Copyright 2026 Marimo. All rights reserved.
"""Internal marimo events for the host stream."""

from __future__ import annotations

import msgspec

from marimo._messaging.notification import NotificationMessage


class MarimoMessage(msgspec.Struct, frozen=True):
    """A marimo notification carried by the host event stream.

    This type is internal to marimo and may change between releases.
    """

    marimo: NotificationMessage
