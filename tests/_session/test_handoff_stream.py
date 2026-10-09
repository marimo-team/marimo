# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest.mock import Mock

import msgspec
import pytest

from marimo._ast.app import App, InternalApp
from marimo._config.manager import get_default_config_manager
from marimo._messaging.attachments import Attachment
from marimo._messaging.notification import AttachmentsNotification
from marimo._messaging.serde import deserialize_kernel_message
from marimo._session.consumer import SessionConsumer
from marimo._session.handoff_stream import (
    MAX_PENDING_EVENTS,
    HandoffStream,
    sse_event,
)
from marimo._session.managers import KernelManagerImpl
from marimo._session.model import ConnectionState
from marimo._session.notebook import AppFileManager
from marimo._session.session import SessionImpl
from marimo._session.state.session_view import SessionView
from marimo._types.ids import ConsumerId

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def agent() -> Attachment:
    return Attachment(id="a1", kind="agent", name="Claude Code", since=1.0)


@pytest.fixture
def other() -> Attachment:
    return Attachment(id="a2", kind="agent", name="Codex", since=2.0)


@pytest.fixture
def handoff() -> dict[str, str]:
    return {"code": "print('π')\n1 / 0", "message": "division by zero"}


@pytest.fixture
def stream_and_changes() -> tuple[HandoffStream, list[list[Attachment]]]:
    changes: list[list[Attachment]] = []
    return HandoffStream(on_attachments_changed=changes.append), changes


def test_sse_event(agent: Attachment) -> None:
    assert sse_event("x", agent) == (
        b'event: x\ndata: {"id":"a1","kind":"agent",'
        b'"name":"Claude Code","since":1.0}\n\n'
    )


def test_sse_payload_preserves_unicode_and_multiline_text(
    handoff: dict[str, str],
) -> None:
    event = sse_event("handoff", handoff)
    lines = event.split(b"\n")
    assert lines[0] == b"event: handoff"
    assert lines[2:] == [b"", b""]
    assert msgspec.json.decode(lines[1][6:]) == handoff


class SelectionHandoff(msgspec.Struct, frozen=True):
    rows: list[int]
    source: str


@dataclass(frozen=True)
class ExtensionPayload:
    message: str


class CustomPayload:
    def _marimo_serialize_(self) -> dict[str, object]:
        return {"selection": [1, 3], "note": "inspect these rows"}


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("inspect the notebook", "inspect the notebook"),
        ({"custom": {"rows": [1, 3]}}, {"custom": {"rows": [1, 3]}}),
        (["plain text", 7, False, None], ["plain text", 7, False, None]),
        (42, 42),
        (True, True),
        (None, None),
        (
            SelectionHandoff(rows=[1, 3], source="third-party"),
            {"rows": [1, 3], "source": "third-party"},
        ),
        (ExtensionPayload(message="inspect π"), {"message": "inspect π"}),
        (CustomPayload(), {"selection": [1, 3], "note": "inspect these rows"}),
    ],
)
def test_publish_accepts_payloads_without_an_error_schema(
    stream_and_changes: tuple[HandoffStream, list[list[Attachment]]],
    agent: Attachment,
    other: Attachment,
    payload: object,
    expected: object,
) -> None:
    stream, _ = stream_and_changes
    client = Attachment(id="c1", kind="client", name=None, since=3.0)
    handles = [stream.attach(value) for value in (agent, other, client)]
    for handle in handles:
        handle.queue.get_nowait()

    stream.publish(payload)

    events = [handle.queue.get_nowait() for handle in handles[:2]]
    assert events[0] == events[1]
    assert events[0] is not None
    lines = events[0].split(b"\n")
    assert lines[0] == b"event: handoff"
    assert lines[2:] == [b"", b""]
    assert msgspec.json.decode(lines[1][6:]) == expected
    assert all(handle.queue.empty() for handle in handles)


def test_attach_notifies_and_queues_only_its_own_attachment(
    stream_and_changes: tuple[HandoffStream, list[list[Attachment]]],
    agent: Attachment,
    other: Attachment,
) -> None:
    stream, changes = stream_and_changes
    first = stream.attach(agent)
    assert first.attachment == agent
    assert first.queue.get_nowait() == sse_event("attached", agent)
    assert first.queue.empty()
    assert any(a.kind == "agent" for a in stream.attachments())

    second = stream.attach(other)
    assert second.queue.get_nowait() == sse_event("attached", other)
    assert second.queue.empty()
    assert first.queue.empty()
    assert stream.attachments() == [agent, other]
    assert changes == [[agent], [agent, other]]


def test_detach_ends_queue_and_notifies_the_remaining_list(
    stream_and_changes: tuple[HandoffStream, list[list[Attachment]]],
    agent: Attachment,
    other: Attachment,
) -> None:
    stream, changes = stream_and_changes
    first = stream.attach(agent)
    first.queue.get_nowait()
    second = stream.attach(other)
    second.queue.get_nowait()

    stream.release(first)

    assert stream.attachments() == [other]
    assert any(a.kind == "agent" for a in stream.attachments())
    assert first.queue.get_nowait() is None
    assert first.queue.empty()
    assert second.queue.empty()
    assert changes == [[agent], [agent, other], [other]]


def test_release_is_idempotent(
    stream_and_changes: tuple[HandoffStream, list[list[Attachment]]],
    agent: Attachment,
) -> None:
    stream, changes = stream_and_changes
    handle = stream.attach(agent)
    handle.queue.get_nowait()
    stream.release(handle)
    stream.release(handle)

    assert stream.attachments() == []
    assert not any(a.kind == "agent" for a in stream.attachments())
    assert handle.queue.get_nowait() is None
    assert handle.queue.empty()
    assert changes == [[agent], []]


def test_reconnect_keeps_since_and_stale_release_preserves_replacement(
    stream_and_changes: tuple[HandoffStream, list[list[Attachment]]],
    agent: Attachment,
    handoff: dict[str, str],
) -> None:
    stream, changes = stream_and_changes
    old_handle = stream.attach(agent)
    old_handle.queue.get_nowait()
    new_handle = stream.attach(
        Attachment(id=agent.id, kind="agent", name="New name", since=99.0)
    )
    replacement = Attachment(
        id=agent.id, kind="agent", name="New name", since=agent.since
    )
    assert old_handle.queue.get_nowait() is None
    assert old_handle.queue.empty()
    assert new_handle.attachment == replacement
    assert new_handle.queue.get_nowait() == sse_event("attached", replacement)

    stream.release(old_handle)
    stream.publish(handoff)

    assert stream.attachments() == [replacement]
    assert changes == [[agent], [replacement]]
    assert old_handle.queue.empty()
    assert new_handle.queue.get_nowait() == sse_event("handoff", handoff)
    assert new_handle.queue.empty()

    stream.release(new_handle)
    assert new_handle.queue.get_nowait() is None
    assert stream.attachments() == []
    assert changes == [[agent], [replacement], []]


def test_publish_fans_out_to_agents_only(
    stream_and_changes: tuple[HandoffStream, list[list[Attachment]]],
    agent: Attachment,
    other: Attachment,
    handoff: dict[str, str],
) -> None:
    stream, changes = stream_and_changes
    client = Attachment(id="c1", kind="client", name=None, since=3.0)
    handles = [stream.attach(value) for value in (agent, other, client)]
    for handle in handles:
        handle.queue.get_nowait()

    stream.publish(handoff)

    for handle in handles[:2]:
        assert handle.queue.get_nowait() == sse_event("handoff", handoff)
        assert handle.queue.empty()
    assert handles[2].queue.empty()
    assert changes == [[agent], [agent, other], [agent, other, client]]


def test_client_does_not_count_as_an_agent(
    stream_and_changes: tuple[HandoffStream, list[list[Attachment]]],
) -> None:
    stream, _ = stream_and_changes
    assert not any(a.kind == "agent" for a in stream.attachments())
    stream.attach(Attachment(id="c1", kind="client", name=None, since=1.0))
    assert not any(a.kind == "agent" for a in stream.attachments())


def test_handoffs_are_not_replayed_on_attach(
    stream_and_changes: tuple[HandoffStream, list[list[Attachment]]],
    agent: Attachment,
    handoff: dict[str, str],
) -> None:
    stream, _ = stream_and_changes
    stream.publish(handoff)
    handle = stream.attach(agent)
    assert handle.queue.get_nowait() == sse_event("attached", agent)
    assert handle.queue.empty()


def test_close_discards_pending_messages_and_ends_every_queue(
    stream_and_changes: tuple[HandoffStream, list[list[Attachment]]],
    agent: Attachment,
    handoff: dict[str, str],
) -> None:
    stream, changes = stream_and_changes
    client = Attachment(id="c1", kind="client", name=None, since=2.0)
    agent_handle = stream.attach(agent)
    client_handle = stream.attach(client)
    stream.publish(handoff)

    stream.close()
    stream.close()
    stream.release(agent_handle)
    stream.release(client_handle)
    stream.publish(handoff)

    assert stream.attachments() == []
    assert not any(a.kind == "agent" for a in stream.attachments())
    assert changes == [[agent], [agent, client], []]
    assert agent_handle.queue.get_nowait() is None
    assert agent_handle.queue.empty()
    assert client_handle.queue.get_nowait() is None
    assert client_handle.queue.empty()
    with pytest.raises(ValueError, match="Handoff stream is closed"):
        stream.attach(agent)


@pytest.mark.parametrize("action", ["close", "release", "replace"])
async def test_termination_unblocks_a_queue_reader(
    stream_and_changes: tuple[HandoffStream, list[list[Attachment]]],
    agent: Attachment,
    action: str,
) -> None:
    stream, _ = stream_and_changes
    handle = stream.attach(agent)
    handle.queue.get_nowait()
    reader = asyncio.create_task(handle.queue.get())
    await asyncio.sleep(0)
    assert not reader.done()

    if action == "close":
        stream.close()
    elif action == "release":
        stream.release(handle)
    else:
        stream.attach(agent)

    assert await asyncio.wait_for(reader, timeout=1) is None


def test_overflow_detaches_only_the_stalled_agent(
    stream_and_changes: tuple[HandoffStream, list[list[Attachment]]],
    agent: Attachment,
    other: Attachment,
) -> None:
    stream, changes = stream_and_changes
    client = Attachment(id="c1", kind="client", name=None, since=3.0)
    slow, healthy, observer = [
        stream.attach(attachment) for attachment in (agent, other, client)
    ]
    for handle in (slow, healthy, observer):
        handle.queue.get_nowait()
        assert handle.queue.maxsize == MAX_PENDING_EVENTS

    for index in range(MAX_PENDING_EVENTS):
        stream.publish(index)
        assert healthy.queue.get_nowait() == sse_event("handoff", index)
    assert slow.queue.full()

    stream.publish("overflow")

    assert stream.attachments() == [other, client]
    assert changes == [
        [agent],
        [agent, other],
        [agent, other, client],
        [other, client],
    ]
    assert slow.queue.get_nowait() is None
    assert slow.queue.empty()
    assert healthy.queue.get_nowait() == sse_event("handoff", "overflow")
    assert observer.queue.empty()

    stream.release(slow)
    stream.publish("later")
    assert healthy.queue.get_nowait() == sse_event("handoff", "later")
    assert slow.queue.empty()


def test_overflow_can_remove_multiple_agents_during_fan_out(
    stream_and_changes: tuple[HandoffStream, list[list[Attachment]]],
    agent: Attachment,
    other: Attachment,
) -> None:
    stream, changes = stream_and_changes
    handles = [stream.attach(attachment) for attachment in (agent, other)]
    for handle in handles:
        handle.queue.get_nowait()
    for index in range(MAX_PENDING_EVENTS):
        stream.publish(index)

    stream.publish("overflow")

    assert stream.attachments() == []
    assert changes == [[agent], [agent, other], [other], []]
    for handle in handles:
        assert handle.queue.get_nowait() is None
        assert handle.queue.empty()


@pytest.mark.parametrize("action", ["close", "release", "replace"])
def test_termination_of_a_full_queue_discards_its_backlog(
    stream_and_changes: tuple[HandoffStream, list[list[Attachment]]],
    agent: Attachment,
    action: str,
) -> None:
    stream, changes = stream_and_changes
    handle = stream.attach(agent)
    handle.queue.get_nowait()
    for index in range(MAX_PENDING_EVENTS):
        stream.publish(index)
    assert handle.queue.full()

    if action == "close":
        stream.close()
    elif action == "release":
        stream.release(handle)
    else:
        replacement = stream.attach(
            Attachment(id=agent.id, kind="agent", name="Replacement", since=99)
        )
        expected = msgspec.structs.replace(agent, name="Replacement")
        assert replacement.attachment == expected
        assert replacement.queue.get_nowait() == sse_event(
            "attached", expected
        )
        stream.release(handle)
        assert stream.attachments() == [expected]
        stream.publish("fresh")
        assert replacement.queue.get_nowait() == sse_event("handoff", "fresh")
        assert replacement.queue.empty()

    assert handle.queue.get_nowait() is None
    assert handle.queue.empty()
    if action != "replace":
        assert stream.attachments() == []
        assert changes == [[agent], []]


@pytest.fixture
def session_and_consumers() -> Iterator[tuple[SessionImpl, list[Mock]]]:
    consumers = [Mock(spec=SessionConsumer) for _ in range(2)]
    for index, consumer in enumerate(consumers):
        consumer.consumer_id = ConsumerId(f"browser-{index}")
        consumer.connection_state.return_value = ConnectionState.OPEN
    session = SessionImpl(
        session_view=SessionView(),
        initialization_id="notebook.py",
        session_consumer=consumers[0],
        kernel_manager=Mock(spec=KernelManagerImpl),
        app_file_manager=AppFileManager.from_app(InternalApp(App())),
        config_manager=get_default_config_manager(current_path=None),
        ttl_seconds=None,
        extensions=[],
    )
    session.connect_consumer(consumers[1], main=False)
    try:
        yield session, consumers
    finally:
        session.close()


def test_session_broadcasts_attachment_changes_to_every_consumer(
    session_and_consumers: tuple[SessionImpl, list[Mock]],
    agent: Attachment,
) -> None:
    session, consumers = session_and_consumers
    handle = session.handoffs.attach(agent)
    session.handoffs.release(handle)

    expected = [
        AttachmentsNotification(attachments=[agent]),
        AttachmentsNotification(attachments=[]),
    ]
    for consumer in consumers:
        assert [
            deserialize_kernel_message(call.args[0])
            for call in consumer.notify.call_args_list
        ] == expected


def test_session_close_ends_handoffs_and_broadcasts_empty_list(
    session_and_consumers: tuple[SessionImpl, list[Mock]],
    agent: Attachment,
) -> None:
    session, consumers = session_and_consumers
    handle = session.handoffs.attach(agent)
    handle.queue.get_nowait()

    session.close()
    session.close()
    session.handoffs.release(handle)

    assert handle.queue.get_nowait() is None
    assert handle.queue.empty()
    assert session.handoffs.attachments() == []
    for consumer in consumers:
        assert [
            deserialize_kernel_message(call.args[0])
            for call in consumer.notify.call_args_list
        ] == [
            AttachmentsNotification(attachments=[agent]),
            AttachmentsNotification(attachments=[]),
        ]
