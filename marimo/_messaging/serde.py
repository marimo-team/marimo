# Copyright 2024 Marimo. All rights reserved.
"""Serialization and deserialization utilities for kernel messages."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from marimo._messaging.msgspec_encoder import encode_json_bytes
from marimo._messaging.types import KernelMessage

if TYPE_CHECKING:
    from marimo._messaging.notifcation import MessageOperation


def serialize_kernel_message(message: msgspec.Struct) -> KernelMessage:
    """
    Serialize a MessageOperation to a KernelMessage.
    """
    return KernelMessage(encode_json_bytes(message))


def deserialize_kernel_message(message: KernelMessage) -> MessageOperation:
    """
    Deserialize a KernelMessage to a MessageOperation.
    """
    # Import here to avoid circular dependency
    from marimo._messaging.notifcation import MessageOperation

    return msgspec.json.decode(message, strict=True, type=MessageOperation)  # type: ignore[no-any-return]


class _OpName(msgspec.Struct):
    op: str


def deserialize_kernel_operation_name(message: KernelMessage) -> str:
    """
    Deserialize a KernelMessage to a MessageOperation name.
    """
    # We use the _OpName type to deserialize the message because it is slimmer than MessageOperation
    return msgspec.json.decode(message, strict=True, type=_OpName).op
