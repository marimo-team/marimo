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
    CATALOG_KINDS,
    NOTEBOOK_KINDS,
    Body,
    Event,
    Stream,
    kind_of,
    message,
)
from tests._core.conftest import ScriptedBackend, names, project


def test_subscriber_failure_does_not_prevent_startup(
    host: Host,
    notebook: Notebook,
    backend: ScriptedBackend,
) -> None:
    def fail(_event: Event) -> None:
        raise RuntimeError("subscriber failed")

    host.subscribe(fail)
    delivered: list[Event] = []
    host.subscribe(delivered.append)

    runtime, created = notebook.start()

    assert created
    assert backend.calls == [("start", runtime.id)]
    assert [e.name for e in delivered] == ["runtime"]


def test_nested_publications_follow_the_current_event() -> None:
    stream = Stream()

    def publish_another(event: Event) -> None:
        if event.id == 1:
            stream.publish(project("p2"))

    stream.subscribe(publish_another)
    delivered: list[Event] = []
    stream.subscribe(delivered.append)

    stream.publish(project())

    assert [e.id for e in delivered] == [1, 2]
    assert delivered == stream.since(0)


def test_readers_cannot_change_other_readers_or_replay() -> None:
    stream = Stream()

    def mutate(event: Event) -> None:
        assert isinstance(event.data, protocol.ProjectMessage)
        with pytest.raises(AttributeError):
            event.data.project.name = "subscriber mutation"
        with pytest.raises(AttributeError):
            event.data.project.operations.clear()

    stream.subscribe(mutate)
    delivered: list[Event] = []
    stream.subscribe(delivered.append)
    original = project()
    published = stream.publish(original)
    with pytest.raises(AttributeError):
        original.name = "caller mutation"

    assert isinstance(published.data, protocol.ProjectMessage)
    assert published.data.project == project()
    with pytest.raises(AttributeError):
        published.data.project.name = "return value mutation"
    assert isinstance(delivered[0].data, protocol.ProjectMessage)
    assert delivered[0].data.project == project()
    with pytest.raises(AttributeError):
        delivered[0].data.project.name = "listener mutation"

    replay = stream.since(0)
    assert replay is not None
    assert isinstance(replay[0].data, protocol.ProjectMessage)
    assert replay[0].data.project == project()
    with pytest.raises(AttributeError):
        replay[0].data.project.name = "replay mutation"
    reread = stream.since(0)
    assert reread is not None
    assert isinstance(reread[0].data, protocol.ProjectMessage)
    assert reread[0].data.project == project()


def test_deferred_events_join_history_before_delivery() -> None:
    stream = Stream()
    delivered: list[Event] = []
    stream.subscribe(delivered.append)

    with stream.deferred():
        stream.publish(project())
        assert [e.id for e in stream.since(0) or []] == [1]
        assert delivered == []

    assert [e.id for e in delivered] == [1]


def test_subscribers_act_after_the_command_reaches_the_backend(
    host: Host, notebook: Notebook, backend: ScriptedBackend
) -> None:
    def stop_on_starting(event: Event) -> None:
        if event.name == "runtime":
            notebook.stop()

    host.subscribe(stop_on_starting, types={"runtime"})

    runtime, _ = notebook.start()

    assert backend.calls == [("start", runtime.id), ("stop", runtime.id)]
    assert notebook.runtime is not None
    assert notebook.runtime.status == "terminating"


def test_subscribers_cannot_interrupt_a_restart(
    host: Host, notebook: Notebook, backend: ScriptedBackend
) -> None:
    runtime, _ = notebook.start()
    notebook.observe(be.Running(runtime.id))
    replacement = notebook.restart()
    backend.calls.clear()
    started: list[tuple[protocol.Runtime, bool]] = []

    def start_on_removal(event: Event) -> None:
        if event.name == "runtime.removed":
            started.append(notebook.start())

    host.subscribe(start_on_removal, types={"runtime"})

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

    def start_on_removal(event: Event) -> None:
        if event.name == "runtime.removed":
            started.append(notebook.start())

    host.subscribe(start_on_removal, types={"runtime"})

    replacement = notebook.adopt(attached.append)

    assert (attached, started, backend.calls) == (
        [replacement.id],
        [(replacement, False)],
        [],
    )


def test_custom_events_are_on_the_notebook_stream_only(
    host: Host, notebook: Notebook
) -> None:
    cursor = host.events(notebook_id=notebook.id)[-1].id
    assert cursor is not None
    custom = notebook.emit("marimo.test", {"hello": 1})

    assert kind_of(custom) == "custom"
    assert names(host.events(cursor, notebook_id=notebook.id)) == [
        "custom",
        "ready",
    ]
    assert "custom" not in names(host.events())
    assert names(
        host.events(cursor, notebook_id=notebook.id, types={"custom"})
    ) == ["custom", "ready"]
    assert names(
        host.events(cursor, notebook_id=notebook.id, types={"attachment"})
    ) == ["ready"]
    replayed = host._stream.since(cursor)
    assert replayed is not None
    assert names(replayed) == ["custom"]


def test_every_body_has_a_kind_a_stream_and_a_message() -> None:
    kinds = {body_type.__name__.lower() for body_type in get_args(Body)}
    assert kinds == CATALOG_KINDS | NOTEBOOK_KINDS
    assert CATALOG_KINDS - NOTEBOOK_KINDS == {"host", "project"}
    for body_type in get_args(Body):
        kind = body_type.__name__.lower()
        wrapper = type(message(_blank(body_type)))
        assert wrapper.__name__ == f"{body_type.__name__}Message"
        assert kind in {
            field.name for field in msgspec.structs.fields(wrapper)
        }
        assert kind_of(_blank(body_type)) == kind


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
