# Copyright 2026 Marimo. All rights reserved.
"""Private wire values shared by agent producers, hosts, and forwarders."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from threading import TIMEOUT_MAX
from typing import Any, Literal

import msgspec

MESSAGE_TYPE = "marimo.agents.pointer.v1"
MESSAGING_HEADER = "Marimo-Agent-Messaging"
ATTACHMENT_HEADER = "Marimo-Agent-Attachment"
REPORT_KEY_HEADER = "Marimo-Agent-Report-Key"
MAX_MESSAGE_BYTES = 4 * 1024 * 1024
MAX_SENDER_LENGTH = 64
SubmissionStatus = Literal["submitted", "rejected", "unknown"]
SubmissionReason = Literal[
    "not-connected",
    "disconnected",
    "timeout",
    "refused",
    "invalid",
    "unconfirmed",
    "failed",
]


class MessageRequest(msgspec.Struct, forbid_unknown_fields=True):
    message_id: str
    message: Any
    to: str | None = None
    broadcast: bool = False
    sender: str | None = None
    timeout: float = 30.0


class PointerEvent(msgspec.Struct, frozen=True):
    message_id: str
    attempt_id: str
    attachment_id: str
    agent_id: str
    sender: str | None


class MessageContent(msgspec.Struct, frozen=True):
    message: Any
    notebook: str
    sender: str | None


class SubmissionReport(msgspec.Struct, forbid_unknown_fields=True):
    attachment_id: str
    attempt_id: str
    status: SubmissionStatus
    reason: SubmissionReason | None = None
    detail: str | None = None


class RecipientResult(msgspec.Struct, frozen=True):
    """The submission outcome for one recipient.

    Args:
        agent_id (str): Selected logical Agent ID.
        name (str | None): Display name, absent for an unknown recipient.
        status (SubmissionStatus): `rejected` permits a safe retry. `unknown`
            means another send can duplicate delivery. `submitted` means
            the harness gave acceptance evidence, not that the model read it.
        reason (SubmissionReason, optional): Cause of the outcome. Absent for
            `submitted`.
        detail (str, optional): Human-readable explanation, at most 500 characters.
    """

    agent_id: str
    name: str | None
    status: SubmissionStatus
    reason: SubmissionReason | None = None
    detail: str | None = None


class SendResult(msgspec.Struct, frozen=True):
    """Submission outcomes for one send or broadcast.

    Args:
        message_id (str): UUID created for this call.
        recipients (tuple[RecipientResult, ...]): One outcome per recipient.
            An empty broadcast has no recipients.
    """

    message_id: str
    recipients: tuple[RecipientResult, ...]


class AgentInfo(msgspec.Struct, frozen=True):
    """A logical agent connection within one Notebook.

    Args:
        id (str): Opaque recipient ID, stable across stream reconnects.
        name (str): Display label. Names are not unique.
    """

    id: str
    name: str


class AgentError(Exception):
    """An operational failure in an agent query, subscription, or send."""


class AgentContextUnavailableError(AgentError):
    """No marimo context exists on the calling thread."""


class SendOutcomeUnknownError(AgentError):
    """The overall response was lost after possible dispatch."""


def validate_sender(sender: str | None) -> None:
    if sender is None:
        return
    if not isinstance(sender, str):
        raise TypeError("sender must be a string")
    if len(sender) > MAX_SENDER_LENGTH or (
        sender and sender.splitlines() != [sender]
    ):
        raise ValueError("sender must be one line of at most 64 characters")


def validate_message_size(message: Any) -> int:
    """Check the encoded content limit and return its size in bytes."""
    size = len(msgspec.json.encode(message))
    if size > MAX_MESSAGE_BYTES:
        raise ValueError("Message exceeds 4 MB of encoded JSON")
    return size


def validate_recipient(to: str) -> None:
    if not isinstance(to, str):
        raise TypeError("to must be a string")
    if not to:
        raise ValueError("to must not be empty")


def validate_timeout(timeout: float) -> float:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise TypeError("timeout must be a number")
    try:
        value = float(timeout)
    except OverflowError as error:
        raise ValueError("timeout must be positive and finite") from error
    if not math.isfinite(value) or value <= 0:
        raise ValueError("timeout must be positive and finite")
    if value > TIMEOUT_MAX:
        raise ValueError("timeout exceeds the platform limit")
    return value


def validate_message(message: Any) -> None:
    """Reject values that cannot cross the JSON seam without conversion."""
    parents: set[int] = set()

    def visit(value: Any) -> None:
        if value is None or isinstance(value, (str, bool, int)):
            return
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("Agent messages require finite numbers")
            return
        if not isinstance(value, (dict, list)):
            raise TypeError("Agent messages require JSON values")
        identity = id(value)
        if identity in parents:
            raise ValueError("Agent messages cannot contain cycles")
        parents.add(identity)
        try:
            if isinstance(value, dict):
                for key, child in value.items():
                    if not isinstance(key, str):
                        raise TypeError("Agent message keys must be strings")
                    visit(child)
            else:
                for child in value:
                    visit(child)
        finally:
            parents.remove(identity)

    visit(message)


@dataclass(frozen=True)
class AgentConnection:
    """Private HTTP connection config for one live editor Session.

    Args:
        url (str): Trusted endpoint prefix for the owning Session.
        auth_token (str): Existing editor authentication token.
        server_token (str): Server version token for POST requests.
    """

    url: str
    auth_token: str = field(repr=False)
    server_token: str = field(repr=False)


class ConnectionSubscriptionRequest(
    msgspec.Struct, forbid_unknown_fields=True
):
    """Private registration addressed through the owning stable Session URL."""

    subscription_id: str
    active: bool = True


def connection_namespace(subscription_id: str) -> str:
    return f"marimo.agents.connections.{subscription_id}"
