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
    Clock,
    ScriptedBackend,
    finish,
    fold,
    host_at,
    names,
    plan,
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


@pytest.mark.parametrize("history", [2, 1000])
def test_expiration_converges_for_live_replay_and_snapshot(
    history: int,
) -> None:
    clock = Clock()
    host, notebook = host_at(clock, history)
    run = notebook.run("code", request_id="request")
    execution = plan(notebook, run, "e")
    item = protocol.Console(
        protocol.ExecutionId("e"),
        protocol.ItemId("console"),
        "stdout",
        0,
        "output",
    )
    notebook.observe(be.Produced(item))
    notebook.observe(
        be.Produced(
            protocol.Display(
                execution_id=execution,
                id=protocol.ItemId("display"),
                seq=1,
                mimetype="text/html",
                data="value",
            )
        )
    )
    finish(notebook, execution)
    notebook.observe(be.Done(run.id, "succeeded"))
    snapshot = host.events(notebook_id=notebook.id, run_id=run.id)
    initial = fold(snapshot)
    assert {kind for kind, _ in initial} == {
        "run",
        "execution",
        "console",
        "display",
    }
    live: list[Event] = []
    host.subscribe(live.append, notebook_id=notebook.id, run_id=run.id)
    clock.now = 9
    host.expire()
    assert live == []
    clock.now = 10
    host.expire()
    assert names(live) == [
        "console.removed",
        "display.removed",
        "execution.removed",
        "run.removed",
    ]
    assert all(event.data.request_id == "request" for event in live)
    replay = host.events(
        snapshot[-1].id, notebook_id=notebook.id, run_id=run.id
    )
    assert (replay[0].name == "reset") == (history == 2)
    assert (
        fold(live, initial)
        == fold(replay, initial)
        == fold(host.events(notebook_id=notebook.id, run_id=run.id))
        == {}
    )
    live.clear()
    notebook.observe(be.Produced(item))
    notebook.observe(be.Status(execution, "running"))
    notebook.observe(be.Done(run.id, "succeeded"))
    assert live == []


def test_cell_results_outlive_ephemeral_members_and_old_runs_are_removed() -> (
    None
):
    clock = Clock()
    host, notebook = host_at(clock)
    run = notebook.run("code", request_id="first")
    ephemeral = plan(notebook, run, "scratch")
    cell = plan(notebook, run, "cell", "a")
    finish(notebook, ephemeral)
    clock.now = 100
    host.expire()
    assert ("execution", ephemeral) in fold(
        host.events(notebook_id=notebook.id)
    )
    finish(notebook, cell)
    notebook.observe(be.Done(run.id, "succeeded"))
    clock.now = 110
    host.expire()
    state = fold(host.events(notebook_id=notebook.id))
    assert set(state) == {("run", run.id), ("execution", cell)}
    replacement = notebook.run("code", request_id="second")
    current = plan(notebook, replacement, "current", "a")
    finish(notebook, current)
    notebook.observe(be.Done(replacement.id, "succeeded"))
    clock.now = 1000
    state = fold(host.events(notebook_id=notebook.id))
    assert set(state) == {("run", replacement.id), ("execution", current)}


def test_run_survives_until_its_last_cell_execution_is_replaced() -> None:
    host, notebook = host_at(Clock())
    original = notebook.run("code", request_id="original")
    first = plan(notebook, original, "first", "a")
    second = plan(notebook, original, "second", "b")
    finish(notebook, first)
    finish(notebook, second)
    notebook.observe(be.Done(original.id, "succeeded"))
    live: list[Event] = []
    host.subscribe(live.append, notebook_id=notebook.id, run_id=original.id)

    replacement = notebook.run("code", request_id="replacement")
    current_a = plan(notebook, replacement, "current-a", "a")
    assert set(fold(host.events(notebook_id=notebook.id))) == {
        ("run", original.id),
        ("run", replacement.id),
        ("execution", second),
        ("execution", current_a),
    }
    assert names(live) == ["execution.removed"]

    current_b = plan(notebook, replacement, "current-b", "b")
    assert set(fold(host.events(notebook_id=notebook.id))) == {
        ("run", replacement.id),
        ("execution", current_a),
        ("execution", current_b),
    }
    assert names(live) == [
        "execution.removed",
        "execution.removed",
        "run.removed",
    ]


def test_stopping_starts_expiry_for_active_work_without_extending_old_results() -> (
    None
):
    clock = Clock()
    host, notebook = host_at(clock)
    done = notebook.run("code", request_id="done")
    execution = plan(notebook, done, "done")
    finish(notebook, execution)
    notebook.observe(be.Done(done.id, "succeeded"))
    clock.now = 5
    active = notebook.run("sleep", request_id="active")
    plan(notebook, active, "active")
    notebook.stop()
    notebook.observe(be.Exited(runtime_id_of(notebook)))
    clock.now = 10
    host.expire()
    state = fold(host.events(notebook_id=notebook.id))
    assert set(state) == {("run", active.id), ("execution", "active")}
    assert state["run", active.id].outcome == "interrupted"
    clock.now = 15
    host.expire()
    assert fold(host.events(notebook_id=notebook.id)) == {}


def test_repeated_expiration_releases_runs_and_request_correlations() -> None:
    clock = Clock()
    host, notebook = host_at(clock, history=2)
    for index in range(100):
        run = notebook.run("code", request_id=f"request-{index}")
        execution = plan(notebook, run, str(index))
        finish(notebook, execution)
        notebook.observe(be.Done(run.id, "succeeded"))
        clock.now += 10
        host.expire()
        assert fold(host.events(notebook_id=notebook.id)) == {}
    assert (
        len({call[1] for call in notebook._backend.calls if call[0] == "run"})
        == 100
    )


def test_removal_listeners_can_read_snapshots() -> None:
    clock = Clock()
    host, notebook = host_at(clock)
    run = notebook.run("code", request_id="request")
    execution = plan(notebook, run, "execution")
    notebook.observe(
        be.Produced(
            protocol.Console(
                execution, protocol.ItemId("console"), "stdout", 0, "x"
            )
        )
    )
    finish(notebook, execution)
    notebook.observe(be.Done(run.id, "succeeded"))
    snapshots: list[dict] = []
    host.subscribe(
        lambda _: snapshots.append(fold(host.events(notebook_id=notebook.id))),
        notebook_id=notebook.id,
    )
    clock.now = 10
    host.expire()
    assert [set(state) for state in snapshots] == [set(), set(), set()]


def test_expiration_does_not_scan_unrelated_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = Clock()
    host, notebook = host_at(clock, history=2)
    run = notebook.run("code", request_id="request")
    for index in range(1000):
        execution = plan(notebook, run, str(index))
        notebook.observe(
            be.Produced(
                protocol.Console(
                    execution, protocol.ItemId(str(index)), "stdout", 0, "x"
                )
            )
        )
        finish(notebook, execution)
    notebook.observe(be.Done(run.id, "succeeded"))
    visits = 0
    getattribute = protocol.Console.__getattribute__

    def counted(item: protocol.Console, name: str) -> object:
        nonlocal visits
        if name == "execution_id":
            visits += 1
        return getattribute(item, name)

    monkeypatch.setattr(protocol.Console, "__getattribute__", counted)
    clock.now = 10
    host.expire()
    assert visits <= 1000
    assert fold(host.events(notebook_id=notebook.id)) == {}


def test_completed_scratch_runs_belong_to_the_host() -> None:
    clock = Clock()
    host, notebook = host_at(clock)
    run = notebook.run("code", request_id="request")
    execution = plan(notebook, run, "scratch")
    notebook.observe(
        be.Produced(
            protocol.Console(
                execution, protocol.ItemId("out"), "stdout", 0, "x"
            )
        )
    )
    assert ("execution", execution) in fold(notebook._snapshot())
    live: list[Event] = []
    host.subscribe(live.append, notebook_id=notebook.id)
    finish(notebook, execution)
    notebook.observe(be.Done(run.id, "succeeded"))
    # The notebook lets go without a word; the host still shows the run.
    assert fold(notebook._snapshot()) == {}
    assert names(live) == ["execution", "execution", "run"]
    assert set(fold(host.events(notebook_id=notebook.id))) == {
        ("run", run.id),
        ("execution", execution),
        ("console", "out"),
    }
    assert notebook._backend.calls.count(("forget", run.id)) == 1
    with pytest.raises(NotFound):
        notebook.interrupt(run.id)
    clock.now = 10
    host.expire()
    assert fold(host.events(notebook_id=notebook.id)) == {}
    assert notebook._backend.calls.count(("forget", run.id)) == 1
