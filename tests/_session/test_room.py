# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.notification import ConsumerCapabilities
from marimo._messaging.serde import deserialize_kernel_message
from marimo._messaging.types import KernelMessage
from marimo._session.consumer import SessionConsumer
from marimo._session.model import ConnectionState
from marimo._session.room import Room
from marimo._types.ids import ConsumerId


class FakeConsumer(SessionConsumer):
    def __init__(self, cid: str) -> None:
        self._cid = ConsumerId(cid)
        self.received: list[KernelMessage] = []
        self.state = ConnectionState.OPEN
        self.detached = False

    @property
    def consumer_id(self) -> ConsumerId:
        return self._cid

    def notify(self, notification: KernelMessage) -> None:
        self.received.append(notification)

    def connection_state(self) -> ConnectionState:
        return self.state

    def on_attach(self, session, event_bus) -> None:  # type: ignore[no-untyped-def]
        del session, event_bus

    def on_detach(self) -> None:
        self.detached = True


def _caps(received: list[KernelMessage]) -> list[ConsumerCapabilities]:
    out: list[ConsumerCapabilities] = []
    for raw in received:
        notif = deserialize_kernel_message(raw)
        if notif.name == "consumer-capabilities":
            out.append(notif.consumer_capabilities)  # type: ignore[attr-defined]
    return out


def _room_with(editor: FakeConsumer, *viewers: FakeConsumer) -> Room:
    room = Room()
    room.add_consumer(editor, main=True)
    for v in viewers:
        room.add_consumer(v, main=False)
    return room


def test_get_consumer_resolves_by_id() -> None:
    a, b = FakeConsumer("a"), FakeConsumer("b")
    room = _room_with(a, b)
    assert room.get_consumer(ConsumerId("b")) is b
    assert room.get_consumer(ConsumerId("missing")) is None


def test_get_capabilities_editor_vs_viewer() -> None:
    a, b = FakeConsumer("a"), FakeConsumer("b")
    room = _room_with(a, b)
    assert room.get_capabilities(a) == ConsumerCapabilities(
        edit=True, interact=True
    )
    assert room.get_capabilities(b) == ConsumerCapabilities(
        edit=False, interact=True
    )


def test_promote_demotes_old_grants_new_no_disconnect() -> None:
    a, b = FakeConsumer("a"), FakeConsumer("b")
    room = _room_with(a, b)

    room.promote_consumer_to_main(b)

    assert room.main_consumer is b
    # both still members; no disconnect
    assert a.consumer_id in room.consumers
    assert b.consumer_id in room.consumers
    # old editor -> interactor caps; new editor -> editor caps
    assert _caps(a.received) == [
        ConsumerCapabilities(edit=False, interact=True)
    ]
    assert _caps(b.received) == [
        ConsumerCapabilities(edit=True, interact=True)
    ]


def test_promote_third_viewer_untouched() -> None:
    a, b, c = FakeConsumer("a"), FakeConsumer("b"), FakeConsumer("c")
    room = _room_with(a, b, c)
    room.promote_consumer_to_main(b)
    assert _caps(c.received) == []


def test_promote_noop_when_already_editor() -> None:
    a = FakeConsumer("a")
    room = _room_with(a)
    room.promote_consumer_to_main(a)
    assert _caps(a.received) == []


def test_promote_skips_closed_consumer() -> None:
    a, b = FakeConsumer("a"), FakeConsumer("b")
    room = _room_with(a, b)
    a.state = ConnectionState.CLOSED
    room.promote_consumer_to_main(b)
    assert _caps(a.received) == []  # closed: not notified
    assert _caps(b.received) == [
        ConsumerCapabilities(edit=True, interact=True)
    ]


def test_stored_capabilities_override_slot() -> None:
    a, b = FakeConsumer("a"), FakeConsumer("b")
    room = Room()
    room.add_consumer(a, main=True)
    # b is not main, but is stamped interact-capable explicitly
    room.add_consumer(
        b,
        main=False,
        capabilities=ConsumerCapabilities(edit=False, interact=True),
    )
    assert room.get_capabilities(b) == ConsumerCapabilities(
        edit=False, interact=True
    )


def test_remove_stale_duplicate_keeps_live_consumer() -> None:
    live = FakeConsumer("a")
    room = _room_with(live)

    stale = FakeConsumer("a")
    room.remove_consumer(stale)

    assert room.get_consumer(ConsumerId("a")) is live
    assert stale.detached
    assert not live.detached


def test_remove_consumer_detaches_and_drops() -> None:
    a, b = FakeConsumer("a"), FakeConsumer("b")
    room = _room_with(a, b)

    room.remove_consumer(b)

    assert b.consumer_id not in room.consumers
    assert b.detached


def test_promote_restamps_stored_capabilities() -> None:
    a, b = FakeConsumer("a"), FakeConsumer("b")
    room = _room_with(a, b)
    room.promote_consumer_to_main(b)
    assert room.get_capabilities(b) == ConsumerCapabilities(
        edit=True, interact=True
    )
    assert room.get_capabilities(a) == ConsumerCapabilities(
        edit=False, interact=True
    )
