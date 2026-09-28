# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal

import msgspec

ParticipantKind = Literal["human", "agent"]
DeliveryStatus = Literal["delivered", "queued", "not_delivered"]
ConsoleChannel = Literal["stdout", "stderr"]


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
