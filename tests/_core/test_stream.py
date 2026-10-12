# Copyright 2026 Marimo. All rights reserved.
"""Event delivery remains ordered and independent of subscribers."""

from __future__ import annotations

from marimo._core import protocol
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.stream import Event, Stream
from tests._core.conftest import ScriptedBackend, project


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
        event.data.project.name = "subscriber mutation"
        event.data.project.operations.clear()

    stream.subscribe(mutate)
    delivered: list[Event] = []
    stream.subscribe(delivered.append)
    original = project()
    published = stream.publish(original)
    original.name = "caller mutation"

    assert isinstance(published.data, protocol.ProjectMessage)
    assert published.data.project == project()
    published.data.project.name = "return value mutation"
    assert isinstance(delivered[0].data, protocol.ProjectMessage)
    assert delivered[0].data.project == project()
    delivered[0].data.project.name = "listener mutation"

    replay = stream.since(0)
    assert replay is not None
    assert isinstance(replay[0].data, protocol.ProjectMessage)
    assert replay[0].data.project == project()
    replay[0].data.project.name = "replay mutation"
    reread = stream.since(0)
    assert reread is not None
    assert isinstance(reread[0].data, protocol.ProjectMessage)
    assert reread[0].data.project == project()
