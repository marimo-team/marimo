# Copyright 2026 Marimo. All rights reserved.
"""Serialization and deserialization utilities for kernel messages."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from marimo._messaging.msgspec_encoder import encode_json_bytes
from marimo._messaging.types import KernelMessage

if TYPE_CHECKING:
    from marimo._messaging.notification import NotificationMessage


def serialize_kernel_message(message: NotificationMessage) -> KernelMessage:
    """
    Serialize a NotificationMessage to a KernelMessage.
    """
    return KernelMessage(encode_json_bytes(message))


def deserialize_kernel_message(message: KernelMessage) -> NotificationMessage:
    """
    Deserialize a KernelMessage to a NotificationMessage.
    """
    # Import here to avoid circular dependency
    from marimo._messaging.notification import NotificationMessage

    return msgspec.json.decode(message, strict=True, type=NotificationMessage)  # type: ignore[no-any-return]


class _NotificationName(msgspec.Struct):
    op: str


def deserialize_kernel_notification_name(message: KernelMessage) -> str:
    """
    Deserialize a KernelMessage to a NotificationMessage name.
    """
    # We use the _NotificationName type to deserialize the message because it is slimmer than NotificationMessage
    return msgspec.json.decode(message, strict=True, type=_NotificationName).op
