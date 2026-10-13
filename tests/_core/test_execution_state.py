# Copyright 2026 Marimo. All rights reserved.
"""Result retention across live streams, replay, and snapshots."""

from __future__ import annotations

import pytest
from msgspec.structs import replace

from marimo._core import backend as be, protocol as p
from marimo._core.execution_state import RetentionPolicy
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.stream import Event
from tests._core.conftest import (
    ScriptedBackend,
    names,
    project,
    record,
    runtime_id_of,
)


class Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now


def host_at(clock: Clock, history: int = 1000) -> tuple[Host, Notebook]:
    host = Host(
        operations=[],
        history=history,
        clock=clock,
        retention=RetentionPolicy(ephemeral_seconds=10),
    )
    host.update_project(project())
    notebook = host.add_notebook(record(), ScriptedBackend())
    notebook.adopt(lambda _: None)
    notebook.observe(be.Running(runtime_id_of(notebook)))
    return host, notebook


def plan(
    notebook: Notebook, run: p.Run, eid: str, cell: str | None = None
) -> p.ExecutionId:
    execution = p.ExecutionId(eid)
    notebook.observe(
        be.Planned(
            run.id,
            (
                be.PlannedExecution(
                    execution, cell, "hash", "code" if cell is None else None
                ),
            ),
        )
    )
    notebook.observe(be.Status(execution, "running"))
    return execution


def finish(notebook: Notebook, execution: p.ExecutionId) -> None:
    notebook.observe(
        be.Concluded(
            execution,
            p.ValueOutcome(p.DisplayData(mimetype="text/plain", data="value")),
        )
    )
    notebook.observe(be.Status(execution, "completed"))


def fold(events: list[Event], initial: dict | None = None) -> dict:
    state = dict(initial or {})
    for event in events:
        if event.name == "reset":
            state.clear()
        elif event.kind in {"run", "execution", "console", "display"}:
            if event.name.endswith(".removed"):
                state.pop((event.kind, event.data.id), None)
            else:
                body = getattr(event.data, event.kind)
                state[event.kind, body.id] = body
    return state


@pytest.mark.parametrize("history", [2, 1000])
def test_expiration_converges_for_live_replay_and_snapshot(
    history: int,
) -> None:
    clock = Clock()
    host, notebook = host_at(clock, history)
    run = notebook.run("code", request_id="request")
    execution = plan(notebook, run, "e")
    item = p.Console(
        p.ExecutionId("e"), p.ItemId("console"), "stdout", 0, "output"
    )
    notebook.observe(be.Produced(item))
    notebook.observe(
        be.Produced(
            p.Display(
                execution_id=execution,
                id=p.ItemId("display"),
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
            p.Console(execution, p.ItemId("console"), "stdout", 0, "x")
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
    assert [set(state) for state in snapshots] == [
        {("run", run.id), ("execution", execution)},
        {("run", run.id)},
        set(),
    ]


@pytest.mark.parametrize("cleanup", ["expire", "replace", "clear"])
def test_outputs_follow_their_execution_through_updates_and_removal(
    cleanup: str,
) -> None:
    clock = Clock()
    host, notebook = host_at(clock)
    run = notebook.run("code", request_id="request")
    first = plan(notebook, run, "first", "a" if cleanup != "expire" else None)
    second = plan(
        notebook, run, "second", "b" if cleanup != "expire" else None
    )
    first_console = p.Console(
        first, p.ItemId("first-console"), "stdout", 0, "a"
    )
    first_display = p.Display(
        execution_id=first,
        id=p.ItemId("first-display"),
        seq=1,
        mimetype="text/plain",
        data="b",
    )
    second_console = p.Console(
        second, p.ItemId("second-console"), "stdout", 0, "c"
    )
    second_display = p.Display(
        execution_id=second,
        id=p.ItemId("second-display"),
        seq=1,
        mimetype="text/plain",
        data="d",
    )
    for item in (second_console, first_console, second_display, first_display):
        notebook.observe(be.Produced(item))
    first_console = replace(first_console, text="updated")
    notebook.observe(be.Produced(first_console))
    finish(notebook, first)
    finish(notebook, second)
    notebook.observe(be.Done(run.id, "succeeded"))
    initial = host.events(notebook_id=notebook.id)
    assert [
        getattr(event.data, event.kind)
        for event in initial
        if event.kind in {"console", "display"}
    ] == [first_console, first_display, second_console, second_display]

    live: list[Event] = []
    snapshots: list[dict] = []

    def updated(event: Event) -> None:
        live.append(event)
        snapshots.append(fold(notebook._snapshot()))

    host.subscribe(
        updated,
        notebook_id=notebook.id,
        types={"run", "execution", "console", "display"},
    )
    if cleanup == "expire":
        clock.now = 10
        host.expire()
    elif cleanup == "replace":
        replacement = notebook.run("code", request_id="replacement")
        plan(notebook, replacement, "new", "a")
    else:
        host.remove_notebook(notebook.id)

    assert [
        (event.name, event.data.id)
        for event in live
        if event.name.endswith(".removed")
    ] == [
        ("console.removed", first_console.id),
        ("display.removed", first_display.id),
        ("execution.removed", first),
        *(
            []
            if cleanup == "replace"
            else [
                ("console.removed", second_console.id),
                ("display.removed", second_display.id),
                ("execution.removed", second),
                ("run.removed", run.id),
            ]
        ),
    ]
    state = fold(initial)
    for event, observed in zip(live, snapshots, strict=True):
        state = fold([event], state)
        assert state == observed


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
                p.Console(execution, p.ItemId(str(index)), "stdout", 0, "x")
            )
        )
        finish(notebook, execution)
    notebook.observe(be.Done(run.id, "succeeded"))
    visits = 0
    getattribute = p.Console.__getattribute__

    def counted(item: p.Console, name: str) -> object:
        nonlocal visits
        if name == "execution_id":
            visits += 1
        return getattribute(item, name)

    monkeypatch.setattr(p.Console, "__getattribute__", counted)
    clock.now = 10
    host.expire()
    assert visits <= 1000
    assert fold(host.events(notebook_id=notebook.id)) == {}


def test_planning_does_not_scan_unrelated_cells(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host, notebook = host_at(Clock(), history=2)
    run = notebook.run("code", request_id="request")
    visits = 0
    getattribute = p.Execution.__getattribute__

    def counted(execution: p.Execution, name: str) -> object:
        nonlocal visits
        if name == "cell_id":
            visits += 1
        return getattribute(execution, name)

    monkeypatch.setattr(p.Execution, "__getattribute__", counted)
    notebook.observe(
        be.Planned(
            run.id,
            tuple(
                be.PlannedExecution(
                    p.ExecutionId(str(index)), str(index), "hash", None
                )
                for index in range(1000)
            ),
        )
    )
    assert visits <= 2000
    assert (
        sum(
            event.kind == "execution"
            for event in host.events(notebook_id=notebook.id)
        )
        == 1000
    )
