# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from marimo._messaging.participants import HandoffPayload
from marimo._session.participants import (
    HandoffTooLargeError,
    NoAttachedParticipantError,
    ParticipantConflictError,
    ParticipantLimits,
    ParticipantRegistry,
    ParticipantRegistryClosedError,
)
from marimo._session.session import SessionImpl
from marimo._session.state.session_view import SessionView
from marimo._session.types import KernelManager


def payload(value: str = "error") -> HandoffPayload:
    return HandoffPayload(
        cell_id="cell-1",
        error=value,
        code="raise RuntimeError()",
        traceback="Traceback\nRuntimeError",
    )


async def test_record_survives_detach_and_resumes_delivery() -> None:
    registry = ParticipantRegistry()
    first = await registry.attach("p1", harness="claude", kind="agent")
    event = await registry.append_handoff(payload())

    detached = await registry.detach("p1")
    before_resume = await registry.delivery_status("p1", event.seq)
    resumed = await registry.attach("p1", harness="changed", kind="human")
    after_resume = await registry.delivery_status("p1", event.seq)
    result = await registry.read_events("p1")

    assert first.cursor == 0
    assert detached.attached is False
    assert before_resume == "not_delivered"
    assert resumed.harness == "claude"
    assert resumed.kind == "agent"
    assert resumed.attached is True
    assert after_resume == "queued"
    assert result.events == (event,)
    assert result.cursor == event.seq
    assert await registry.delivery_status("p1", event.seq) == "delivered"
    registry.close()


async def test_different_live_participant_is_rejected() -> None:
    registry = ParticipantRegistry()
    await registry.attach("p1", harness="claude", kind="agent")

    with pytest.raises(ParticipantConflictError) as error:
        await registry.attach("p2", harness="codex", kind="agent")

    assert error.value.holder_harness == "claude"
    assert await registry.state("p2") is None
    registry.close()


async def test_reads_use_cursor_since_and_limit() -> None:
    registry = ParticipantRegistry()
    await registry.attach("p1", harness="claude", kind="agent")
    events = tuple(
        [
            await registry.append_handoff(payload(str(index)))
            for index in range(3)
        ]
    )

    first = await registry.read_events("p1", limit=1)
    rest = await registry.read_events("p1")
    replay = await registry.read_events("p1", since=0, limit=2)

    assert first.events == events[:1]
    assert first.cursor == 1
    assert first.remaining == 2
    assert rest.events == events[1:]
    assert rest.cursor == 3
    assert rest.remaining == 0
    assert replay.events == events[:2]
    assert replay.cursor == 3
    assert replay.remaining == 1
    registry.close()


async def test_retention_drops_oldest_without_false_delivery() -> None:
    registry = ParticipantRegistry(retained_event_limit=2)
    await registry.attach("p1", harness="claude", kind="agent")
    first = await registry.append_handoff(payload("first"))
    second = await registry.append_handoff(payload("second"))
    third = await registry.append_handoff(payload("third"))

    result = await registry.read_events("p1")

    assert result.events == (second, third)
    assert result.cursor == third.seq
    assert await registry.delivery_status("p1", first.seq) == ("not_delivered")
    registry.close()


async def test_delivered_history_can_be_evicted() -> None:
    registry = ParticipantRegistry(retained_event_limit=1)
    await registry.attach("p1", harness="claude", kind="agent")
    first = await registry.append_handoff(payload("first"))
    await registry.read_events("p1")

    second = await registry.append_handoff(payload("second"))

    assert await registry.delivery_status("p1", first.seq) == "delivered"
    assert (await registry.read_events("p1")).events == (second,)
    registry.close()


async def test_inactive_record_bound_drops_oldest_on_attach() -> None:
    registry = ParticipantRegistry(inactive_record_limit=1)
    await registry.attach("p1", harness="claude", kind="agent")
    await registry.detach("p1")
    await registry.attach("p2", harness="codex", kind="agent")
    await registry.detach("p2")

    current = await registry.attach("p3", harness="opencode", kind="agent")

    assert await registry.state("p1") is None
    assert await registry.state("p2") is not None
    assert current.participant_id == "p3"
    registry.close()


async def test_sequence_is_monotonic_per_participant() -> None:
    registry = ParticipantRegistry()
    await registry.attach("p1", harness="claude", kind="agent")
    first = await registry.append_handoff(payload())
    await registry.detach("p1")
    await registry.attach("p2", harness="codex", kind="agent")
    other = await registry.append_handoff(payload())
    await registry.detach("p2")
    await registry.attach("p1", harness="claude", kind="agent")
    second = await registry.append_handoff(payload())

    assert (first.seq, second.seq) == (1, 2)
    assert other.seq == 1
    registry.close()


async def test_payload_cap_rejects_handoff_before_append() -> None:
    registry = ParticipantRegistry(payload_cap_bytes=150)
    await registry.attach("p1", harness="claude", kind="agent")

    with pytest.raises(HandoffTooLargeError):
        await registry.append_handoff(payload("x" * 100))

    event = await registry.append_handoff(payload("x"))
    assert event.seq == 1
    registry.close()


async def test_handoff_requires_a_live_attachment() -> None:
    registry = ParticipantRegistry()

    with pytest.raises(NoAttachedParticipantError):
        await registry.append_handoff(payload())

    registry.close()


async def test_ttl_ends_attachment_but_keeps_record() -> None:
    registry = ParticipantRegistry(ttl_seconds=0.01)
    snapshots = []
    registry.set_presence_callback(snapshots.append)
    await registry.attach("p1", harness="claude", kind="agent")

    await asyncio.sleep(0.02)

    state = await registry.current_state()
    assert state is not None
    assert state.participant_id == "p1"
    assert state.attached is False
    assert [snapshot.attached for snapshot in snapshots] == [True, False]
    registry.close()


async def test_repeat_contact_renews_ttl() -> None:
    now = 0.0
    registry = ParticipantRegistry(ttl_seconds=120, clock=lambda: now)
    await registry.attach("p1", harness="claude", kind="agent")

    now = 100.0
    await registry.attach("p1", harness="claude", kind="agent")
    now = 130.0
    renewed = await registry.current_state()
    now = 221.0
    expired = await registry.current_state()

    assert renewed is not None
    assert renewed.attached is True
    assert expired is not None
    assert expired.attached is False
    registry.close()


async def test_stream_delivers_retained_and_future_events() -> None:
    registry = ParticipantRegistry()
    await registry.attach("p1", harness="claude", kind="agent")
    first = await registry.append_handoff(payload("first"))
    stream = registry.stream_events("p1")

    assert await anext(stream) == first
    second = await registry.append_handoff(payload("second"))
    assert await anext(stream) == second
    await stream.aclose()

    state = await registry.state("p1")
    assert state is not None
    assert state.cursor == second.seq
    assert state.listening is False
    assert state.attached is True
    registry.close()


async def test_detach_closes_event_stream() -> None:
    registry = ParticipantRegistry(sse_keepalive_seconds=60)
    await registry.attach("p1", harness="claude", kind="agent")
    stream = registry.stream_events("p1")
    waiting = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)

    listening = await registry.state("p1")
    assert listening is not None
    assert listening.listening is True

    await registry.detach("p1")

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(waiting, timeout=1)
    registry.close()


async def test_session_close_closes_event_stream() -> None:
    registry = ParticipantRegistry(sse_keepalive_seconds=60)
    await registry.attach("p1", harness="claude", kind="agent")
    stream = registry.stream_events("p1")
    waiting = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)

    registry.close()

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(waiting, timeout=1)


async def test_replacement_stream_keeps_new_listener_active() -> None:
    registry = ParticipantRegistry(sse_keepalive_seconds=60)
    await registry.attach("p1", harness="claude", kind="agent")
    first_stream = registry.stream_events("p1")
    first_waiting = asyncio.create_task(anext(first_stream))
    await asyncio.sleep(0)
    second_stream = registry.stream_events("p1")
    second_waiting = asyncio.create_task(anext(second_stream))
    await asyncio.sleep(0)

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(first_waiting, timeout=1)
    state = await registry.state("p1")
    assert state is not None
    assert state.listening is True

    event = await registry.append_handoff(payload())
    assert await asyncio.wait_for(second_waiting, timeout=1) == event
    await second_stream.aclose()
    registry.close()


async def test_event_stream_emits_keepalive_ticks() -> None:
    registry = ParticipantRegistry(sse_keepalive_seconds=0.01)
    await registry.attach("p1", harness="claude", kind="agent")
    stream = registry.stream_events("p1")

    assert await anext(stream) is None

    await stream.aclose()
    registry.close()


async def test_inline_read_respects_budget_and_advances_cursor() -> None:
    registry = ParticipantRegistry(inline_budget_bytes=300)
    await registry.attach("p1", harness="claude", kind="agent")
    token = await registry.begin_request("p1")
    assert token is not None
    first = await registry.append_handoff(payload("x" * 100))
    second = await registry.append_handoff(payload("y" * 100))

    result = await registry.read_inline_events("p1", token)

    assert result is not None
    assert result.events == (first,)
    assert result.cursor == first.seq
    assert result.remaining == 1
    assert await registry.delivery_status("p1", first.seq) == "delivered"
    assert await registry.delivery_status("p1", second.seq) == "queued"
    registry.close()


async def test_inline_read_omits_detached_participant() -> None:
    registry = ParticipantRegistry()
    await registry.attach("p1", harness="claude", kind="agent")
    token = await registry.begin_request("p1")
    assert token is not None
    event = await registry.append_handoff(payload())
    await registry.detach("p1")

    result = await registry.read_inline_events("p1", token)

    assert result is None
    assert await registry.delivery_status("p1", event.seq) == "not_delivered"
    registry.close()


async def test_stale_request_does_not_consume_after_reattach() -> None:
    registry = ParticipantRegistry()
    await registry.attach("p1", harness="claude", kind="agent")
    stale_token = await registry.begin_request("p1")
    assert stale_token is not None
    event = await registry.append_handoff(payload())
    await registry.detach("p1")
    await registry.attach("p1", harness="claude", kind="agent")

    result = await registry.read_inline_events("p1", stale_token)

    assert result is None
    assert await registry.delivery_status("p1", event.seq) == "queued"
    registry.close()


async def test_overlapping_requests_keep_activity_until_the_last_end() -> None:
    registry = ParticipantRegistry(wall_clock=lambda: 1_234.5)
    snapshots = []
    registry.set_presence_callback(snapshots.append)
    await registry.attach("p1", harness="claude", kind="agent")

    first = await registry.begin_request("p1")
    second = await registry.begin_request("p1")
    assert first is not None
    assert second is not None
    await registry.end_request("p1", first)
    still_active = await registry.state("p1")
    await registry.end_request("p1", second)
    inactive = await registry.state("p1")

    assert still_active is not None
    assert still_active.active is True
    assert still_active.active_since == 1_234.5
    assert inactive is not None
    assert inactive.active is False
    assert inactive.active_since is None
    assert [snapshot.active for snapshot in snapshots] == [False, True, False]
    registry.close()


async def test_request_end_after_detach_is_ignored() -> None:
    registry = ParticipantRegistry()
    await registry.attach("p1", harness="claude", kind="agent")
    token = await registry.begin_request("p1")
    assert token is not None

    detached = await registry.detach("p1")
    await registry.end_request("p1", token)
    after_end = await registry.state("p1")

    assert detached.active is False
    assert after_end == detached
    registry.close()


async def test_presence_snapshot_fields_use_wall_time() -> None:
    snapshots = []
    registry = ParticipantRegistry(wall_clock=lambda: 1_234.5)
    registry.set_presence_callback(snapshots.append)

    attached = await registry.attach("p1", harness="claude", kind="agent")
    detached = await registry.detach("p1")

    assert snapshots == [attached, detached]
    assert attached.last_contact_at == 1_234.5
    assert attached.listening is False
    assert attached.active is False
    assert attached.active_since is None
    registry.close()


def test_limits_validate_bounds() -> None:
    with pytest.raises(ValueError, match="positive"):
        ParticipantLimits(ttl_seconds=0)
    with pytest.raises(ValueError, match="negative"):
        ParticipantLimits(inactive_record_limit=-1)


def test_registry_exposes_approved_default_limits() -> None:
    registry = ParticipantRegistry()

    assert registry.limits == ParticipantLimits(
        payload_cap_bytes=256 * 1024,
        retained_event_limit=500,
        ttl_seconds=120,
        listener_grace_seconds=10,
        sse_keepalive_seconds=15,
        inline_budget_bytes=32 * 1024,
        inactive_record_limit=4,
    )
    registry.close()


async def test_session_close_releases_participant_records() -> None:
    registry = ParticipantRegistry()
    await registry.attach("p1", harness="claude", kind="agent")
    session = SessionImpl(
        initialization_id="notebook.py",
        session_consumer=None,
        session_view=SessionView(),
        kernel_manager=MagicMock(spec=KernelManager),
        app_file_manager=MagicMock(),
        config_manager=MagicMock(),
        ttl_seconds=None,
        extensions=[],
        participant_registry=registry,
    )

    session.close()

    with pytest.raises(ParticipantRegistryClosedError):
        await registry.state("p1")
