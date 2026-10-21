# Copyright 2026 Marimo. All rights reserved.
"""Agent message values shared by producers and delivery adapters."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

import msgspec

MESSAGE_TYPE = "marimo.agents.message.v1"
MESSAGING_HEADER = "Marimo-Agent-Messaging"
ATTACHMENT_HEADER = "Marimo-Agent-Attachment"
REPORT_KEY_HEADER = "Marimo-Agent-Report-Key"

SubmissionStatus = Literal["submitted", "rejected", "unknown"]


class AgentInfo(msgspec.Struct, frozen=True):
    """A logical agent connection within one Notebook.

    Args:
        id (str): Opaque recipient ID, stable across stream reconnects.
        name (str | None): Optional display label. Names are not unique.
    """

    id: str
    name: str | None


class RecipientResult(msgspec.Struct, frozen=True):
    """The observed submission outcome for one selected agent.

    Args:
        agent_id (str): The selected logical agent ID.
        status (str): `submitted`, `rejected`, or `unknown`.
        detail (str | None, optional): Explanation of the observed outcome.
    """

    agent_id: str
    status: SubmissionStatus
    detail: str | None = None


class SendResult(msgspec.Struct, frozen=True):
    """Submission outcomes for the recipients selected at acceptance.

    Args:
        recipients (tuple[RecipientResult, ...]): One result per recipient.
    """

    recipients: tuple[RecipientResult, ...]


class AgentMessagingError(Exception):
    """An operational failure in agent messaging."""


class MessagingUnavailableError(AgentMessagingError):
    """The current context has no live editor messaging adapter."""


class NoAgentsConnectedError(AgentMessagingError):
    """A broadcast has no connected recipients."""


class SendOutcomeUnknownError(AgentMessagingError):
    """The overall response was lost after possible dispatch."""


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


class MessageRequest(msgspec.Struct, forbid_unknown_fields=True):
    """Private producer request with an explicit recipient policy."""

    message: Any
    to: str | None = None
    broadcast: bool = False
    timeout: float = 30.0


class SubmissionReport(msgspec.Struct, forbid_unknown_fields=True):
    """Private outcome bound to one stream and one submission attempt."""

    attachment_id: str
    attempt_id: str
    status: SubmissionStatus
    detail: str | None = None


class MessageError(msgspec.Struct):
    """A definite failure before message dispatch on the internal HTTP API."""

    code: Literal["unavailable", "no-agents", "invalid-argument", "failed"]
    detail: str


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
