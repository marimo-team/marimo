# Copyright 2026 Marimo. All rights reserved.
"""Host catalogs, snapshots, and event subscriptions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from msgspec import UNSET
from msgspec.structs import replace

from marimo._core import backend as be, protocol
from marimo._core.errors import NotFound
from marimo._core.host import Host
from marimo._core.stream import Event
from tests._core.conftest import (
    ScriptedBackend,
    names,
    project,
    record,
    runtime_id_of,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._core.notebook import Notebook


def test_catalog_snapshot_and_replay_exclude_runs(host: Host) -> None:
    host.update_project(project())
    notebook = host.add_notebook(record(), ScriptedBackend())
    notebook.start()
    notebook.observe(be.Running(runtime_id_of(notebook)))
    run = notebook.run("1", request_id="r1")
    cursor = host.events()[-1].id
    assert cursor is not None

    notebook.observe(
        be.Planned(
            run.id,
            (be.PlannedExecution(protocol.ExecutionId("e1"), None, "h", "1"),),
        )
    )
    notebook.attach()

    events = host.events()
    assert names(events) == [
        "host",
        "project",
        "notebook",
        "runtime",
        "attachment",
        "ready",
    ]
    assert all(e.id is None for e in events[:-1])
    assert events[-1].id == cursor + 2
    assert all(getattr(e.data, "time", None) is UNSET for e in events[:-1])
    assert names(host.events(cursor)) == ["attachment", "ready"]


def test_a_notebook_stream_sees_only_its_notebook(host: Host) -> None:
    host.update_project(project())
    first = host.add_notebook(record("n1", "a.py"), ScriptedBackend())
    second = host.add_notebook(record("n2", "b.py"), ScriptedBackend())
    first.start()
    first.observe(be.Running(runtime_id_of(first)))
    run = first.run("1", request_id="r1")
    first.observe(
        be.Planned(
            run.id,
            (be.PlannedExecution(protocol.ExecutionId("e1"), None, "h", "1"),),
        )
    )
    second.start()

    events = host.events(notebook_id="n1")
    assert names(events) == [
        "notebook",
        "runtime",
        "run",
        "execution",
        "ready",
    ]
    assert all(e.notebook_id == "n1" for e in events[:-1])

    # Replay includes both starting and running states for n1.
    live = host.events(0, notebook_id="n1")
    assert names(live) == [
        "notebook",
        "runtime",
        "runtime",
        "run",
        "execution",
        "ready",
    ]
    assert all(e.id is not None for e in live)

    with pytest.raises(NotFound):
        host.events(notebook_id="n3")


def test_resume_replays_or_resets() -> None:
    small = Host(operations=[], history=2)
    small.update_project(project())
    small.add_notebook(record(), ScriptedBackend())
    cursor = small.events()[-1].id
    assert cursor is not None

    assert names(small.events(cursor)) == ["ready"]
    small.update_project(project("p2"))
    assert names(small.events(cursor)) == ["project", "ready"]
    small.update_project(project("p3"))
    small.update_project(project("p4"))
    assert names(small.events(cursor))[0] == "reset"
    assert names(small.events(10**6))[0] == "reset"


def test_types_filter_keeps_ready_and_reset(host: Host) -> None:
    host.update_project(project())
    host.add_notebook(record(), ScriptedBackend())
    assert names(host.events(types={"notebook"})) == ["notebook", "ready"]
    assert names(host.events(10**6, types={"notebook"})) == [
        "reset",
        "notebook",
        "ready",
    ]


def test_subscribe_filters_the_live_stream(host: Host) -> None:
    host.update_project(project())
    notebook = host.add_notebook(record(), ScriptedBackend())
    catalog: list[Event] = []
    mine: list[Event] = []
    runtimes: list[Event] = []
    host.subscribe(catalog.append)
    host.subscribe(mine.append, notebook_id="n1")
    unsubscribe = host.subscribe(runtimes.append, types={"runtime"})

    notebook.start()
    notebook.observe(be.Running(runtime_id_of(notebook)))
    run = notebook.run("1", request_id="r1")
    unsubscribe()
    host.update_project(project("p2"))

    assert names(catalog) == ["runtime", "runtime", "project"]
    assert names(mine) == ["runtime", "runtime", "run"]
    assert names(runtimes) == ["runtime", "runtime"]


def test_removing_a_notebook_removes_what_it_owns_first(host: Host) -> None:
    host.update_project(project())
    notebook = host.add_notebook(record(), ScriptedBackend())
    notebook.start()
    notebook.observe(be.Running(runtime_id_of(notebook)))
    notebook.attach()
    run = notebook.run("1", request_id="r1")
    log: list[Event] = []
    host.subscribe(log.append, notebook_id="n1")

    host.remove_notebook("n1", request_id="req-del")

    assert names(log) == [
        "run",
        "run.removed",
        "attachment.removed",
        "runtime.removed",
        "notebook.removed",
    ]
    assert getattr(log[-1].data, "request_id", None) == "req-del"
    assert "n1" not in host.notebooks
    with pytest.raises(NotFound):
        host.notebook(notebook.id)
    host.remove_notebook("n1")  # Repeated removal is a no-op.


def test_updating_a_notebook_publishes_only_changes(host: Host) -> None:
    host.update_project(project())
    backend = ScriptedBackend()
    notebook = host.add_notebook(record(), backend)
    notebook.start()
    notebook.observe(be.Running(runtime_id_of(notebook)))
    run = notebook.run("1", request_id="run")
    runtime = notebook.runtime
    backend.calls.clear()
    log: list[Event] = []
    host.subscribe(log.append, notebook_id="n1")

    host.update_notebook(record())
    host.update_project(project())
    moved = record(path="moved.py")
    host.update_notebook(moved, request_id="req-mv")

    assert host.notebooks[notebook.id] == moved
    assert host.notebook("n1") is notebook
    assert notebook.runtime is runtime
    assert backend.calls == []
    assert host.events(notebook_id="n1", types={"run"})[
        0
    ].data == protocol.RunMessage(run=run, request_id="run")
    assert host.events(notebook_id="n1")[0].data == protocol.NotebookMessage(
        notebook=moved
    )
    assert host.events(types={"notebook"})[0].data == protocol.NotebookMessage(
        notebook=moved
    )
    assert names(log) == ["notebook"]
    assert getattr(log[0].data, "request_id", None) == "req-mv"
    with pytest.raises(NotFound):
        host.update_notebook(record("n9"))
    with pytest.raises(ValueError, match="project"):
        host.update_notebook(
            replace(moved, project_id=protocol.ProjectId("missing"))
        )
    assert host.notebooks[notebook.id] == moved


def test_removed_notebook_handles_cannot_be_reused(
    host: Host,
    notebook: Notebook,
    backend: ScriptedBackend,
    log: list[Event],
) -> None:
    runtime, _ = notebook.start()
    notebook.observe(be.Running(runtime.id))
    run = notebook.run("1", request_id="r1")
    attachment = notebook.attach()
    retained_id = notebook.id
    host.remove_notebook(retained_id)
    backend.calls.clear()
    log.clear()

    commands: list[Callable[[], object]] = [
        notebook.start,
        lambda: notebook.adopt(lambda _: None),
        notebook.stop,
        notebook.restart,
        lambda: notebook.run("1", request_id=run.id),
        lambda: notebook.interrupt(run.id),
        notebook.attach,
    ]
    for command in commands:
        with pytest.raises(NotFound, match="no notebook"):
            command()

    # Late backend updates and disconnect cleanup cannot revive the notebook.
    notebook.observe(be.Starting(runtime.id, "Late startup"))
    notebook.observe(be.Running(runtime.id))
    notebook.observe(be.Exited(runtime.id))
    notebook.detach(attachment.id)
    host.remove_notebook(retained_id)

    assert backend.calls == []
    assert log == []
    assert notebook.runtime is None


def test_catalog_requires_the_project(host: Host) -> None:
    with pytest.raises(ValueError, match="project"):
        host.add_notebook(record(), ScriptedBackend())
    host.update_project(project())
    host.add_notebook(record(), ScriptedBackend())
    with pytest.raises(ValueError, match="already"):
        host.add_notebook(record(), ScriptedBackend())


def test_catalog_updates_do_not_share_mutable_records(host: Host) -> None:
    source = project()
    host.update_project(source)
    with pytest.raises(AttributeError):
        source.name = "changed"
    source = replace(source, name="changed", operations=())
    host.update_project(source)

    replay = host.events(0, types={"project"})
    projects = [
        e.data.project
        for e in replay
        if isinstance(e.data, protocol.ProjectMessage)
    ]
    assert projects == [
        project(),
        replace(project(), name="changed", operations=()),
    ]

    original = record()
    host.add_notebook(original, ScriptedBackend())
    with pytest.raises(AttributeError):
        original.name = "caller mutation"
    original = replace(original, name="caller mutation", operations=())
    view = host.notebooks[original.id]
    with pytest.raises(AttributeError):
        view.name = "reader mutation"
    assert host.notebooks[original.id] == record()

    host.update_notebook(original)
    with pytest.raises(AttributeError):
        original.name = "another mutation"
    assert host.notebooks[original.id] == replace(
        record(), name="caller mutation", operations=()
    )
