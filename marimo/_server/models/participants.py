# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import msgspec

from marimo._messaging.participants import (
    HandoffEvent,
    HarnessMetadata,
    ParticipantKind,
)


class ParticipantAttachResponse(msgspec.Struct, rename="camel"):
    participant_id: str
    cursor: int
    attached: bool
    record_created: bool
    kind: ParticipantKind
    harness: HarnessMetadata


class ParticipantDetachResponse(msgspec.Struct, rename="camel"):
    participant_id: str
    attached: bool


class ParticipantEventsResponse(msgspec.Struct, rename="camel"):
    events: tuple[HandoffEvent, ...]
    cursor: int
    remaining: int


class ParticipantHandoffResponse(msgspec.Struct, rename="camel"):
    seq: int
