# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal

import msgspec

ParticipantKind = Literal["human", "agent"]
DeliveryStatus = Literal["delivered", "queued", "not_delivered"]
ConsoleChannel = Literal["stdout", "stderr"]


def _validate_metadata_field(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty.")
    if len(value) > 128:
        raise ValueError(f"{name} must not exceed 128 characters.")
    if not value.isprintable():
        raise ValueError(f"{name} must contain only printable characters.")


class HarnessMetadata(msgspec.Struct, frozen=True, rename="camel"):
    """Harness identity supplied by the participant."""

    id: str
    display_name: str

    def __post_init__(self) -> None:
        _validate_metadata_field(self.id, "harness.id")
        _validate_metadata_field(self.display_name, "harness.display_name")


class ParticipantMetadata(msgspec.Struct, frozen=True, rename="camel"):
    """Self-described participant details cached by the Session."""

    kind: ParticipantKind = "agent"
    harness: HarnessMetadata = HarnessMetadata(
        id="unknown", display_name="Agent"
    )


DEFAULT_PARTICIPANT_METADATA = ParticipantMetadata()


class HandoffConsoleOutput(msgspec.Struct, frozen=True, rename="camel"):
    channel: ConsoleChannel
    data: str


class HandoffPayload(msgspec.Struct, frozen=True, rename="camel"):
    cell_id: str
    error: str
    code: str
    traceback: str
    console_tail: tuple[HandoffConsoleOutput, ...] = ()
    note: str | None = None


class HandoffEvent(msgspec.Struct, frozen=True, rename="camel"):
    seq: int
    created_at: float
    cell_id: str
    error: str
    code: str
    traceback: str
    console_tail: tuple[HandoffConsoleOutput, ...] = ()
    note: str | None = None
