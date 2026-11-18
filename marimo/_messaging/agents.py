# Copyright 2026 Marimo. All rights reserved.
"""Private wire values shared by agent producers, hosts, and forwarders."""

from __future__ import annotations

from typing import Any, Literal

import msgspec

MESSAGE_TYPE = "marimo.agents.pointer.v1"
MESSAGING_HEADER = "Marimo-Agent-Messaging"
ATTACHMENT_HEADER = "Marimo-Agent-Attachment"
REPORT_KEY_HEADER = "Marimo-Agent-Report-Key"
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
    agent_id: str
    name: str | None
    status: SubmissionStatus
    reason: SubmissionReason | None = None
    detail: str | None = None


class SendResult(msgspec.Struct, frozen=True):
    message_id: str
    recipients: tuple[RecipientResult, ...]
