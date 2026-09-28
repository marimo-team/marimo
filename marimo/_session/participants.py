# Copyright 2026 Marimo. All rights reserved.
"""Session-local participant records and handoff logs."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import msgspec

from marimo._messaging.participants import (
    DeliveryStatus,
    HandoffEvent,
    HandoffPayload,
    ParticipantKind,
)

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class ParticipantLimits:
    payload_cap_bytes: int = 256 * 1024
    retained_event_limit: int = 500
    ttl_seconds: float = 120
    listener_grace_seconds: float = 10
    sse_keepalive_seconds: float = 15
    inline_budget_bytes: int = 32 * 1024
    inactive_record_limit: int = 4

    def __post_init__(self) -> None:
        positive = (
            self.payload_cap_bytes,
            self.ttl_seconds,
            self.listener_grace_seconds,
            self.sse_keepalive_seconds,
            self.inline_budget_bytes,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("Participant limits must be positive.")
        if self.retained_event_limit < 0 or self.inactive_record_limit < 0:
            raise ValueError("Participant bounds must not be negative.")


@dataclass(frozen=True)
class ParticipantState:
    participant_id: str
    harness: str
    kind: ParticipantKind
    cursor: int
    attached: bool
    listening: bool
    active: bool
    last_contact_at: float
    active_since: float | None


@dataclass(frozen=True)
class EventRead:
    events: tuple[HandoffEvent, ...]
    cursor: int
    remaining: int


class ParticipantRegistryError(Exception):
    """Base error for participant registry operations."""


class ParticipantRegistryClosedError(ParticipantRegistryError):
    """The owning Session has closed."""


class ParticipantConflictError(ParticipantRegistryError):
    """A different participant has a live attachment."""

    def __init__(self, holder_harness: str) -> None:
        super().__init__(holder_harness)
        self.holder_harness = holder_harness


class ParticipantNotFoundError(ParticipantRegistryError):
    """The participant record does not exist."""


class NoAttachedParticipantError(ParticipantRegistryError):
    """No participant can receive a handoff."""


class HandoffTooLargeError(ParticipantRegistryError):
    """The structured handoff exceeds the configured payload cap."""


@dataclass
class _ParticipantRecord:
    participant_id: str
    harness: str
    kind: ParticipantKind
    last_contact_at: float
    order: int
    cursor: int = 0
    next_seq: int = 1
    attached: bool = False
    listening: bool = False
    active: bool = False
    active_since: float | None = None
    expires_at: float | None = None
    attachment_generation: int = 0
    events: list[HandoffEvent] = field(default_factory=list)
    evicted_unread_ranges: list[tuple[int, int]] = field(default_factory=list)

    def state(self) -> ParticipantState:
        return ParticipantState(
            participant_id=self.participant_id,
            harness=self.harness,
            kind=self.kind,
            cursor=self.cursor,
            attached=self.attached,
            listening=self.listening,
            active=self.active,
            last_contact_at=self.last_contact_at,
            active_since=self.active_since,
        )


class ParticipantRegistry:
    """Own participant lifetime and handoff delivery for one Session."""

    def __init__(
        self,
        *,
        payload_cap_bytes: int = 256 * 1024,
        retained_event_limit: int = 500,
        ttl_seconds: float = 120,
        listener_grace_seconds: float = 10,
        sse_keepalive_seconds: float = 15,
        inline_budget_bytes: int = 32 * 1024,
        inactive_record_limit: int = 4,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self.limits = ParticipantLimits(
            payload_cap_bytes=payload_cap_bytes,
            retained_event_limit=retained_event_limit,
            ttl_seconds=ttl_seconds,
            listener_grace_seconds=listener_grace_seconds,
            sse_keepalive_seconds=sse_keepalive_seconds,
            inline_budget_bytes=inline_budget_bytes,
            inactive_record_limit=inactive_record_limit,
        )
        self._clock = clock
        self._wall_clock = wall_clock
        self._presence_callback: Callable[[ParticipantState], None] | None = (
            None
        )
        self._records: dict[str, _ParticipantRecord] = {}
        self._expiry_tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()
        self._next_order = 0
        self._closed = False

    async def attach(
        self,
        participant_id: str,
        *,
        harness: str,
        kind: ParticipantKind,
    ) -> ParticipantState:
        """Create or resume a record and start a new attachment."""
        async with self._lock:
            self._ensure_open()
            now = self._clock()
            self._expire_due(now)
            holder = self._attached_record()
            if holder is not None and holder.participant_id != participant_id:
                raise ParticipantConflictError(holder.harness)

            record = self._records.get(participant_id)
            contacted_at = self._wall_clock()
            if record is None:
                record = _ParticipantRecord(
                    participant_id=participant_id,
                    harness=harness,
                    kind=kind,
                    last_contact_at=contacted_at,
                    order=self._next_order,
                )
                self._next_order += 1
                self._records[participant_id] = record

            record.last_contact_at = contacted_at
            record.attached = True
            record.expires_at = now + self.limits.ttl_seconds
            record.attachment_generation += 1
            self._prune_inactive_records()
            self._schedule_expiry(record)
            state = record.state()
            self._emit_presence(state)
            return state

    async def detach(self, participant_id: str) -> ParticipantState:
        """End an attachment while retaining its record and handoff log."""
        async with self._lock:
            self._ensure_open()
            record = self._record(participant_id)
            self._end_attachment(record)
            return record.state()

    def set_presence_callback(
        self, callback: Callable[[ParticipantState], None]
    ) -> None:
        """Send future presence transitions through the owning Session."""
        self._presence_callback = callback

    async def append_handoff(self, payload: HandoffPayload) -> HandoffEvent:
        """Append one structured handoff to the live participant's log."""
        if len(msgspec.json.encode(payload)) > self.limits.payload_cap_bytes:
            raise HandoffTooLargeError

        async with self._lock:
            self._ensure_open()
            self._expire_due(self._clock())
            record = self._attached_record()
            if record is None:
                raise NoAttachedParticipantError
            event = HandoffEvent(
                seq=record.next_seq,
                created_at=self._clock(),
                cell_id=payload.cell_id,
                error=payload.error,
                code=payload.code,
                traceback=payload.traceback,
                console_tail=payload.console_tail,
                note=payload.note,
            )
            record.next_seq += 1
            record.events.append(event)
            self._trim_events(record)
            return event

    async def read_events(
        self,
        participant_id: str,
        *,
        since: int | None = None,
        limit: int | None = None,
    ) -> EventRead:
        """Read retained events and move the server cursor only forward."""
        if since is not None and since < 0:
            raise ValueError("since must not be negative.")
        if limit is not None and limit < 0:
            raise ValueError("limit must not be negative.")

        async with self._lock:
            self._ensure_open()
            record = self._record(participant_id)
            threshold = record.cursor if since is None else since
            pending = [
                event for event in record.events if event.seq > threshold
            ]
            selected = pending if limit is None else pending[:limit]
            if selected:
                record.cursor = max(record.cursor, selected[-1].seq)
            return EventRead(
                events=tuple(selected),
                cursor=record.cursor,
                remaining=len(pending) - len(selected),
            )

    async def delivery_status(
        self, participant_id: str, seq: int
    ) -> DeliveryStatus:
        """Derive delivery from cursor, attachment, and retention loss."""
        async with self._lock:
            self._ensure_open()
            record = self._record(participant_id)
            if self._was_evicted_unread(record, seq):
                return "not_delivered"
            if seq <= record.cursor:
                return "delivered"
            return "queued" if record.attached else "not_delivered"

    async def state(self, participant_id: str) -> ParticipantState | None:
        """Return an immutable view of one record."""
        async with self._lock:
            self._ensure_open()
            record = self._records.get(participant_id)
            return None if record is None else record.state()

    async def current_state(self) -> ParticipantState | None:
        """Return the live record, or the most recently contacted record."""
        async with self._lock:
            self._ensure_open()
            self._expire_due(self._clock())
            record = self._attached_record()
            if record is None and self._records:
                record = max(
                    self._records.values(),
                    key=lambda item: (item.last_contact_at, item.order),
                )
            return None if record is None else record.state()

    def close(self) -> None:
        """Release every record and timer owned by the Session."""
        if self._closed:
            return
        self._closed = True
        self._presence_callback = None
        for task in self._expiry_tasks.values():
            task.cancel()
        self._expiry_tasks.clear()
        self._records.clear()

    def _record(self, participant_id: str) -> _ParticipantRecord:
        record = self._records.get(participant_id)
        if record is None:
            raise ParticipantNotFoundError(participant_id)
        return record

    def _attached_record(self) -> _ParticipantRecord | None:
        return next(
            (record for record in self._records.values() if record.attached),
            None,
        )

    def _end_attachment(self, record: _ParticipantRecord) -> None:
        presence_changed = record.attached or record.listening or record.active
        record.attached = False
        record.listening = False
        record.active = False
        record.active_since = None
        record.expires_at = None
        task = self._expiry_tasks.pop(record.participant_id, None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()
        if presence_changed:
            self._emit_presence(record.state())

    def _schedule_expiry(self, record: _ParticipantRecord) -> None:
        previous = self._expiry_tasks.pop(record.participant_id, None)
        if previous is not None:
            previous.cancel()
        task = asyncio.create_task(
            self._expire_attachment(
                record.participant_id, record.attachment_generation
            ),
            name=f"participant.expire.{record.participant_id}",
        )
        self._expiry_tasks[record.participant_id] = task

    async def _expire_attachment(
        self, participant_id: str, generation: int
    ) -> None:
        try:
            while True:
                async with self._lock:
                    if self._closed:
                        return
                    record = self._records.get(participant_id)
                    if (
                        record is None
                        or not record.attached
                        or record.attachment_generation != generation
                        or record.expires_at is None
                    ):
                        return
                    remaining = record.expires_at - self._clock()
                    if remaining <= 0:
                        self._end_attachment(record)
                        return
                await asyncio.sleep(remaining)
        except asyncio.CancelledError:
            return

    def _expire_due(self, now: float) -> None:
        for record in self._records.values():
            if (
                record.attached
                and record.expires_at is not None
                and record.expires_at <= now
            ):
                self._end_attachment(record)

    def _prune_inactive_records(self) -> None:
        inactive = sorted(
            (
                record
                for record in self._records.values()
                if not record.attached
            ),
            key=lambda item: (item.last_contact_at, item.order),
        )
        excess = len(inactive) - self.limits.inactive_record_limit
        for record in inactive[: max(excess, 0)]:
            self._records.pop(record.participant_id, None)
            task = self._expiry_tasks.pop(record.participant_id, None)
            if task is not None:
                task.cancel()

    def _trim_events(self, record: _ParticipantRecord) -> None:
        excess = len(record.events) - self.limits.retained_event_limit
        if excess <= 0:
            return
        removed = record.events[:excess]
        del record.events[:excess]
        unread = [event.seq for event in removed if event.seq > record.cursor]
        if unread:
            start, end = unread[0], unread[-1]
            ranges = record.evicted_unread_ranges
            if ranges and ranges[-1][1] + 1 == start:
                ranges[-1] = (ranges[-1][0], end)
            else:
                ranges.append((start, end))

    @staticmethod
    def _was_evicted_unread(record: _ParticipantRecord, seq: int) -> bool:
        return any(
            start <= seq <= end for start, end in record.evicted_unread_ranges
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise ParticipantRegistryClosedError

    def _emit_presence(self, state: ParticipantState) -> None:
        callback = self._presence_callback
        if callback is not None:
            callback(state)
