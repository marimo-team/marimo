# Copyright 2026 Marimo. All rights reserved.
"""Event delivery remains ordered and independent of subscribers."""

from __future__ import annotations

from typing import get_args

import msgspec
import pytest

from marimo._core import backend as be, protocol
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.stream import (
    ExtensionEvent,
    RoutedEvent,
    Stream,
    event_name,
    removal,
)
from tests._core.conftest import ScriptedBackend, names, project


def test_subscriber_failure_does_not_prevent_startup(
    host: Host,
    notebook: Notebook,
    backend: ScriptedBackend,
) -> None:
    def fail(_event: RoutedEvent) -> None:
        raise RuntimeError("subscriber failed")

    host.subscribe(fail)
    delivered: list[RoutedEvent] = []
    host.subscribe(delivered.append)

    runtime, created = notebook.start()

    assert created
    assert backend.calls == [("start", runtime.id)]
    assert [event_name(e.event) for e in delivered] == ["runtime"]


def test_nested_publications_follow_the_current_event() -> None:
    stream = Stream()

    def publish_another(event: RoutedEvent) -> None:
        if event.position == 1:
            stream.publish(project("p2"))

    stream.subscribe(publish_another)
    delivered: list[RoutedEvent] = []
    stream.subscribe(delivered.append)

    stream.publish(project())

    assert [e.position for e in delivered] == [1, 2]
    assert delivered == stream.since(0)


def test_readers_cannot_change_other_readers_or_replay() -> None:
    stream = Stream()

    def mutate(event: RoutedEvent) -> None:
        assert isinstance(event.event, protocol.ProjectEvent)
        with pytest.raises(AttributeError):
            event.event.data.project.name = "subscriber mutation"
        with pytest.raises(AttributeError):
            event.event.data.project.operations.clear()

    stream.subscribe(mutate)
    delivered: list[RoutedEvent] = []
    stream.subscribe(delivered.append)
    original = project()
    published = stream.publish(original)
    with pytest.raises(AttributeError):
        original.name = "caller mutation"

    assert isinstance(published.event, protocol.ProjectEvent)
    assert published.event.data.project == project()
    with pytest.raises(AttributeError):
        published.event.data.project.name = "return value mutation"
    assert isinstance(delivered[0].event, protocol.ProjectEvent)
    assert delivered[0].event.data.project == project()
    with pytest.raises(AttributeError):
        delivered[0].event.data.project.name = "listener mutation"

    replay = stream.since(0)
    assert replay is not None
    assert isinstance(replay[0].event, protocol.ProjectEvent)
    assert replay[0].event.data.project == project()
    with pytest.raises(AttributeError):
        replay[0].event.data.project.name = "replay mutation"
    reread = stream.since(0)
    assert reread is not None
    assert isinstance(reread[0].event, protocol.ProjectEvent)
    assert reread[0].event.data.project == project()


def test_a_record_is_shared_by_the_log_its_listeners_and_its_readers() -> None:
    stream = Stream()
    delivered: list[RoutedEvent] = []
    stream.subscribe(delivered.append)
    original = project()

    published = stream.publish(original)

    assert isinstance(published.event, protocol.ProjectEvent)
    assert published.event.record is original
    assert delivered == [published]
    assert delivered[0] is published
    replay = stream.since(0)
    assert replay is not None
    assert replay[0] is published


def test_deferred_events_join_history_before_delivery() -> None:
    stream = Stream()
    delivered: list[RoutedEvent] = []
    stream.subscribe(delivered.append)

    with stream.deferred():
        stream.publish(project())
        assert [e.position for e in stream.since(0) or []] == [1]
        assert delivered == []

    assert [e.position for e in delivered] == [1]


def test_subscribers_act_after_the_command_reaches_the_backend(
    host: Host, notebook: Notebook, backend: ScriptedBackend
) -> None:
    def stop_on_starting(event: RoutedEvent) -> None:
        if isinstance(event.event, protocol.RuntimeEvent):
            notebook.stop().unwrap()

    host.subscribe(stop_on_starting, kinds={"runtime"})

    runtime, _ = notebook.start()

    assert backend.calls == [("start", runtime.id), ("stop", runtime.id)]
    assert notebook.runtime is not None
    assert notebook.runtime.state == protocol.RuntimeStopping()


def test_subscribers_cannot_interrupt_a_restart(
    host: Host, notebook: Notebook, backend: ScriptedBackend
) -> None:
    runtime, _ = notebook.start()
    notebook.observe(be.Running(runtime.id))
    replacement = notebook.restart().unwrap()
    backend.calls.clear()
    started: list[tuple[protocol.Runtime, bool]] = []

    def start_on_removal(event: RoutedEvent) -> None:
        if isinstance(event.event, protocol.RuntimeRemovedEvent):
            started.append(notebook.start())

    host.subscribe(start_on_removal, kinds={"runtime"})

    notebook.observe(be.Exited(runtime.id))

    assert backend.calls == [("start", replacement.id)]
    assert started == [(replacement, False)]


def test_subscribers_cannot_start_a_runtime_during_adoption(
    host: Host, notebook: Notebook, backend: ScriptedBackend
) -> None:
    runtime, _ = notebook.start()
    notebook.observe(be.Exited(runtime.id, "Kernel died"))
    backend.calls.clear()
    started: list[tuple[protocol.Runtime, bool]] = []
    attached: list[protocol.RuntimeId] = []

    def start_on_removal(event: RoutedEvent) -> None:
        if isinstance(event.event, protocol.RuntimeRemovedEvent):
            started.append(notebook.start())

    host.subscribe(start_on_removal, kinds={"runtime"})

    replacement = notebook.adopt(attached.append)

    assert (attached, started, backend.calls) == (
        [replacement.id],
        [(replacement, False)],
        [],
    )


def test_custom_events_are_on_the_notebook_stream_only(
    host: Host, notebook: Notebook
) -> None:
    ready = host.events(notebook_id=notebook.id)[-1]
    cursor = ready.event.id
    assert isinstance(cursor, str)
    assert cursor is not None
    payload: dict[str, protocol.JsonValue] = {"hello": 1}
    notebook.emit("marimo.test", payload)
    payload["hello"] = 2

    assert names(host.events(cursor, notebook_id=notebook.id)) == [
        "custom",
        "ready",
    ]
    assert "custom" not in names(host.events())
    assert names(
        host.events(cursor, notebook_id=notebook.id, kinds={"custom"})
    ) == ["custom", "ready"]
    assert names(
        host.events(cursor, notebook_id=notebook.id, kinds={"attachment"})
    ) == ["ready"]
    replayed = host._stream.since(ready.position or 0)
    assert replayed is not None
    assert names(replayed) == ["custom"]
    event = replayed[0].event
    assert isinstance(event, protocol.CustomEvent)
    assert event.data.custom.data == {"hello": 1}


def test_every_body_has_a_kind_a_stream_and_a_typed_event() -> None:
    for body_type in get_args(protocol.events.Body):
        kind = body_type.__name__.lower()
        event = Stream().publish(
            _blank(body_type),
            notebook_id=protocol.NotebookId("n1"),
        )
        assert type(event.event).__name__ == f"{body_type.__name__}Event"
        assert event_name(event.event) == kind
        wrapper = type(event.event.data)
        assert wrapper.__name__ == f"{body_type.__name__}Message"
        assert kind in {
            field.name for field in msgspec.structs.fields(wrapper)
        }
        assert event.wanted({kind})
        assert not event.wanted({"unknown"})
        assert event.event.record == _blank(body_type)
        assert event.visible_in(None) == (
            kind in {"host", "project", "notebook", "runtime", "attachment"}
        )
        assert event.visible_in("n1") == (kind not in {"host", "project"})
        assert not event.visible_in("n2")


@pytest.mark.parametrize(
    "record_type", get_args(protocol.events.RemovableBody)
)
def test_removals_preserve_scope_and_type_filters(
    record_type: type[protocol.events.RemovableBody],
) -> None:
    kind = record_type.__name__.lower()
    event = removal(record_type, "item", notebook_id=protocol.NotebookId("n1"))
    assert event.visible_in(None) == (
        kind in {"project", "notebook", "runtime", "attachment"}
    )
    assert event.visible_in("n1") == (kind != "project")
    assert not event.visible_in("n2")
    assert event.wanted({kind})
    assert not event.wanted({"host"})


def test_extension_type_filters_preserve_the_full_wire_name() -> None:
    class Removed(msgspec.Struct, frozen=True):
        id: str

    class Extension(ExtensionEvent, tag="extension.removed"):
        pass

    event = RoutedEvent(Extension(Removed(id="item")))
    assert [
        event.wanted(kinds)
        for kinds in (None, {"extension.removed"}, {"extension"})
    ] == [True, True, False]


def _blank(body_type: type[msgspec.Struct]) -> msgspec.Struct:
    """Build a body with placeholder values, enough to wrap it."""
    values = {}
    for field in msgspec.structs.fields(body_type):
        if field.required:
            values[field.name] = _placeholder(field.type)
    return body_type(**values)


def _placeholder(annotation: object) -> object:
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())
    if origin is not None and args:
        return _placeholder(args[0])
    if annotation is str:
        return "x"
    if annotation is int:
        return 0
    if annotation is bool:
        return False
    if annotation is float:
        return 0.0
    if isinstance(annotation, type) and issubclass(annotation, msgspec.Struct):
        return _blank(annotation)
    return None
