# Copyright 2026 Marimo. All rights reserved.
"""Run and execution transitions, without a stream or a backend."""

from __future__ import annotations

import dataclasses

import pytest
from dirty_equals import IsDatetime
from msgspec.structs import replace

from marimo._core import backend as be, protocol
from marimo._core.document import Document, DocumentCell
from marimo._core.errors import NoRuntime
from marimo._core.executions import (
    CellExecution,
    Change,
    Executions,
    Released,
    Removed,
)
from marimo._core.stream import utcnow
from tests._core.conftest import retained_execution

NOTEBOOK = protocol.NotebookId("n1")
RUNTIME = protocol.Runtime(
    id=protocol.RuntimeId("rt-1"),
    notebook_id=NOTEBOOK,
    marimo_version=None,
    created_at=utcnow(),
    state=protocol.RuntimeReady(),
)


def run(run_id: str) -> protocol.Run:
    return protocol.Run(
        id=protocol.RunId(run_id),
        notebook_id=NOTEBOOK,
        runtime_id=RUNTIME.id,
        origin=protocol.RunRuntimeOrigin(),
        created_at=utcnow(),
        state=protocol.RunQueued(),
    )


def planned(run_id: str, *executions: tuple[str, str | None]) -> be.Planned:
    """Plan executions as `(id, cell_id)` pairs; a `None` cell is scratch."""
    return be.Planned(
        protocol.RunId(run_id),
        tuple(
            be.PlannedExecution(
                protocol.ExecutionId(eid),
                cell,
                "hash",
            )
            for eid, cell in executions
        ),
    )


def complete(
    executions: Executions,
    eid: str,
    outcome: protocol.ExecutionOutcome | None = None,
) -> list[Change]:
    execution = protocol.ExecutionId(eid)
    changes: list[Change] = []
    for msg in (
        be.Started(execution),
        be.Completed(execution, outcome or protocol.SucceededOutcome()),
    ):
        changes.extend(executions.observe(msg, RUNTIME))
    return changes


def describe(changes: list[Change]) -> list[str]:
    """Render changes as `kind id`, with `.removed` and `released` marked."""
    out: list[str] = []
    for change in changes:
        if isinstance(change, Released):
            out.append(f"released {change.run_id}")
        elif isinstance(change, Removed):
            out.append(
                f"{change.record_type.__name__.lower()}.removed {change.id}"
            )
        else:
            out.append(f"{type(change).__name__.lower()} {change.id}")
    return out


def variable(execution_id: str = "e1") -> protocol.Variable:
    return protocol.Variable(
        execution_id=protocol.ExecutionId(execution_id),
        id=protocol.ItemId("v1"),
        name="x",
        preview="1",
        revision=protocol.Revision(protocol.ExecutionId(execution_id), 0),
        type="int",
    )


def test_clear_console_removes_only_this_executions_output_items() -> None:
    executions = Executions()
    executions.begin(run("r1"), "request")
    [queued] = executions.observe(planned("r1", ("e1", "a")), RUNTIME)
    assert isinstance(queued, protocol.Execution)
    eid = queued.id
    executions.observe(be.Started(eid), RUNTIME)
    for item in (
        protocol.Console(
            id=protocol.ItemId("text"),
            execution_id=eid,
            seq=0,
            content=protocol.ConsoleText(stream="stdout", text="hello"),
        ),
        protocol.Console(
            id=protocol.ItemId("plot"),
            execution_id=eid,
            seq=1,
            content=protocol.ConsoleMedia(
                protocol.Media(mimetype="text/html", data="plot")
            ),
        ),
        protocol.Input(
            id=protocol.ItemId("prompt"),
            execution_id=eid,
            seq=2,
            prompt="?",
            password=False,
            status="pending",
        ),
    ):
        executions.observe(be.Produced(item), RUNTIME)
    clear = be.ConsoleCleared(eid)
    assert describe(executions.observe(clear, RUNTIME)) == [
        "console.removed text",
        "console.removed plot",
    ]
    assert executions.observe(clear, RUNTIME) == []
    assert describe(executions._records()) == [
        "run r1",
        "execution e1",
        "input prompt",
    ]


@pytest.mark.parametrize("started", [False, True])
def test_completion_freezes_the_outcome_and_input_revisions(
    started: bool,
) -> None:
    executions = Executions()
    executions.begin(run("r1"), "request")
    [queued] = executions.observe(planned("r1", ("e1", "a")), RUNTIME)
    assert isinstance(queued, protocol.Execution)
    eid = queued.id
    if started:
        executions.observe(be.Started(eid), RUNTIME)
        executions.observe(be.Displayed(eid, None), RUNTIME)
    inputs = {
        "x": protocol.Revision(protocol.ExecutionId("producer"), 2),
        "print": None,
    }
    completed = be.Completed(eid, protocol.CancelledOutcome(), inputs)
    assert executions.observe(completed, RUNTIME) == [
        replace(
            queued,
            state=protocol.ExecutionCompleted(
                started_at=IsDatetime() if started else None,
                completed_at=IsDatetime(),
                outcome=protocol.CancelledOutcome(),
                depends_on=inputs,
            ),
        )
    ]
    retained = executions.current(protocol.CellId("a"))
    inputs.clear()
    for message in (
        be.Started(eid),
        be.Completed(eid, protocol.SucceededOutcome()),
    ):
        assert executions.observe(message, RUNTIME) == []
    assert executions.current(protocol.CellId("a")) == retained


def test_a_cell_result_outlives_its_run_until_the_next_replaces_it() -> None:
    executions = Executions()
    executions.begin(run("r1"), "first")
    executions.observe(planned("r1", ("e1", "a")), RUNTIME)
    bound = variable()
    assert executions.observe(be.Produced(bound), RUNTIME) == [bound]
    complete(executions, "e1")
    done = executions.observe(
        be.Done(protocol.RunId("r1"), "succeeded"), RUNTIME
    )
    assert describe(done) == ["run r1"]
    assert executions.active() is None
    assert describe(executions._records()) == [
        "run r1",
        "execution e1",
        "variable v1",
    ]
    assert executions.request_id(protocol.RunId("r1")) == "first"
    assert executions.snapshot_request(protocol.RunId("r1")) is None

    before = executions.current(protocol.CellId("a"))
    assert before is not None
    updated = replace(
        bound, preview="2", revision=replace(bound.revision, update=1)
    )
    assert executions.observe(be.Produced(updated), RUNTIME) == [updated]
    assert executions.current(protocol.CellId("a")) == dataclasses.replace(
        before, variables=(updated,)
    )
    assert before.variables == (bound,)

    executions.begin(run("r2"), "second")
    replaced = executions.observe(planned("r2", ("e2", "a")), RUNTIME)
    assert describe(replaced) == [
        "variable.removed v1",
        "execution.removed e1",
        "released r1",
        "execution e2",
    ]
    executions.release(protocol.RunId("r1"))
    assert executions.run(protocol.RunId("r1")) is None
    assert describe(executions._records()) == ["run r2", "execution e2"]
    assert executions.observe(be.Produced(updated), RUNTIME) == []


def test_late_display_updates_preserve_completion_and_stop_after_replacement() -> (
    None
):
    executions = Executions()
    executions.begin(run("r1"), "first")
    executions.observe(planned("r1", ("e1", "a")), RUNTIME)
    complete(executions, "e1")
    executions.observe(be.Done(protocol.RunId("r1"), "succeeded"), RUNTIME)
    before = executions.current(protocol.CellId("a"))
    assert before is not None
    completed_run = executions.run(protocol.RunId("r1"))
    for display in (
        protocol.Media(mimetype="text/plain", data="late"),
        None,
    ):
        expected = protocol.Output(
            id=protocol.ItemId("e1:output"),
            execution_id=protocol.ExecutionId("e1"),
            media=display,
        )
        assert executions.observe(
            be.Displayed(protocol.ExecutionId("e1"), display), RUNTIME
        ) == [expected]
        assert executions.current(protocol.CellId("a")) == dataclasses.replace(
            before, output=expected
        )
        assert executions.run(protocol.RunId("r1")) == completed_run
    executions.begin(run("r2"), "second")
    executions.observe(planned("r2", ("e2", "a")), RUNTIME)
    assert (
        executions.observe(
            be.Displayed(protocol.ExecutionId("e1"), None), RUNTIME
        )
        == []
    )


def test_scratch_work_leaves_with_its_run() -> None:
    executions = Executions()
    executions.begin(run("r1"), "request")
    executions.observe(planned("r1", ("e1", None)), RUNTIME)
    assert executions.observe(be.Produced(variable()), RUNTIME) == []
    produced = executions.observe(
        be.Produced(
            protocol.Console(
                id=protocol.ItemId("c1"),
                execution_id=protocol.ExecutionId("e1"),
                seq=0,
                content=protocol.ConsoleText(stream="stdout", text="x"),
            )
        ),
        RUNTIME,
    )
    assert describe(produced) == ["console c1"]
    assert executions.run_id_of(produced[0]) == "r1"
    complete(executions, "e1")
    done = executions.observe(
        be.Done(protocol.RunId("r1"), "succeeded"), RUNTIME
    )
    assert describe(done) == ["run r1", "released r1"]
    executions.release(protocol.RunId("r1"))
    assert executions._records() == []


def test_a_kernel_exit_fails_the_running_execution_and_cancels_the_queued() -> (
    None
):
    executions = Executions()
    executions.begin(run("r1"), "request")
    executions.observe(planned("r1", ("e1", "a"), ("e2", "b")), RUNTIME)
    executions.observe(be.Started(protocol.ExecutionId("e1")), RUNTIME)

    ended = executions.interrupt(failure="killed")

    outcomes = {
        change.id: change.state.outcome
        for change in ended
        if isinstance(change, protocol.Execution)
        and isinstance(change.state, protocol.ExecutionCompleted)
    }
    running = outcomes[protocol.ExecutionId("e1")]
    assert isinstance(running, protocol.ExecutionFailedOutcome)
    assert (running.error.kind, running.error.message) == (
        "internal",
        "killed",
    )
    assert outcomes[protocol.ExecutionId("e2")] == protocol.CancelledOutcome()
    assert [
        change.state.outcome
        for change in ended
        if isinstance(change, protocol.Run)
        and isinstance(change.state, protocol.RunCompleted)
    ] == [protocol.RunFailedOutcome(message="killed")]


def test_a_run_completes_only_after_its_executions_and_reports_failures() -> (
    None
):
    executions = Executions()
    executions.begin(run("r1"), "request")
    executions.observe(planned("r1", ("e1", "a")), RUNTIME)
    executions.observe(be.Started(protocol.ExecutionId("e1")), RUNTIME)
    with pytest.raises(ValueError, match="unfinished"):
        executions.observe(be.Done(protocol.RunId("r1"), "succeeded"), RUNTIME)
    complete(executions, "e1", protocol.CancelledOutcome())
    with pytest.raises(ValueError, match="successful"):
        executions.observe(be.Done(protocol.RunId("r1"), "succeeded"), RUNTIME)
    done = executions.observe(be.Done(protocol.RunId("r1"), "failed"), RUNTIME)
    assert [
        change.state.outcome
        for change in done
        if isinstance(change, protocol.Run)
        and isinstance(change.state, protocol.RunCompleted)
    ] == [protocol.RunFailedOutcome(message=None)]


def test_a_run_with_skipped_cells_succeeds() -> None:
    executions = Executions()
    executions.begin(run("r1"), "request")
    executions.observe(planned("r1", ("e1", "a"), ("e2", "b")), RUNTIME)
    for eid in ("e1", "e2"):
        executions.observe(be.Started(protocol.ExecutionId(eid)), RUNTIME)
    complete(executions, "e1")
    complete(
        executions,
        "e2",
        protocol.ExecutionSkippedOutcome(
            reason="upstream-stopped",
            message="This cell wasn't run because an ancestor was stopped",
            related=(),
        ),
    )
    done = executions.observe(
        be.Done(protocol.RunId("r1"), "succeeded"), RUNTIME
    )
    assert [
        change.state.outcome
        for change in done
        if isinstance(change, protocol.Run)
        and isinstance(change.state, protocol.RunCompleted)
    ] == [protocol.SucceededOutcome()]
    assert executions.current(protocol.CellId("b")) is not None


def test_interrupting_completes_everything_in_flight() -> None:
    executions = Executions()
    executions.begin(run("r1"), "request")
    executions.observe(planned("r1", ("e1", "a"), ("e2", None)), RUNTIME)
    for eid in ("e1", "e2"):
        executions.observe(be.Started(protocol.ExecutionId(eid)), RUNTIME)
    changes = executions.interrupt()
    assert describe(changes) == ["execution e1", "execution e2", "run r1"]
    assert all(
        isinstance(change.state, protocol.ExecutionCompleted)
        and isinstance(change.state.outcome, protocol.CancelledOutcome)
        for change in changes
        if isinstance(change, protocol.Execution)
    )
    # The scratch execution is forgotten silently; the cell result stays.
    assert describe(executions._records()) == ["run r1", "execution e1"]


def test_clearing_removes_results_and_releases_runs() -> None:
    executions = Executions()
    executions.begin(run("r1"), "request")
    executions.observe(planned("r1", ("e1", "a")), RUNTIME)
    executions.observe(
        be.Produced(
            protocol.Console(
                id=protocol.ItemId("c1"),
                execution_id=protocol.ExecutionId("e1"),
                seq=0,
                content=protocol.ConsoleText(stream="stdout", text="x"),
            )
        ),
        RUNTIME,
    )
    complete(executions, "e1")
    executions.observe(be.Done(protocol.RunId("r1"), "succeeded"), RUNTIME)
    assert describe(executions.clear()) == [
        "console.removed c1",
        "execution.removed e1",
        "released r1",
    ]


def test_scheduling_needs_a_runtime_but_stray_updates_do_not() -> None:
    executions = Executions()
    with pytest.raises(NoRuntime):
        executions.observe(
            be.Scheduled(protocol.RunId("r1"), protocol.RunRuntimeOrigin()),
            None,
        )
    assert (
        executions.observe(be.Started(protocol.ExecutionId("e1")), None) == []
    )
    scheduled = executions.observe(
        be.Scheduled(protocol.RunId("r1"), protocol.RunRuntimeOrigin()),
        RUNTIME,
    )
    assert describe(scheduled) == ["run r1"]
    (published,) = scheduled
    assert isinstance(published, protocol.Run)
    assert published.origin == protocol.RunRuntimeOrigin()
    assert executions.request_id(protocol.RunId("r1")) is None


def test_planning_does_not_scan_unrelated_cells(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executions = Executions()
    executions.begin(run("r1"), "request")
    visits = 0
    getattribute = protocol.Execution.__getattribute__

    def counted(execution: protocol.Execution, name: str) -> object:
        nonlocal visits
        if name == "cell_id":
            visits += 1
        return getattribute(execution, name)

    monkeypatch.setattr(protocol.Execution, "__getattribute__", counted)
    changes = executions.observe(
        planned("r1", *((str(index), str(index)) for index in range(1000))),
        RUNTIME,
    )
    assert visits <= 3000
    assert sum(isinstance(c, protocol.Execution) for c in changes) == 1000


def test_removing_a_cell_drops_its_result_or_disowns_active_work() -> None:
    executions = Executions()
    executions.begin(run("r1"), "request")
    executions.observe(planned("r1", ("e1", "a"), ("e2", "b")), RUNTIME)
    complete(executions, "e1")
    executions.observe(be.Started(protocol.ExecutionId("e2")), RUNTIME)
    assert describe(executions.remove_cell(protocol.CellId("a"))) == [
        "execution.removed e1"
    ]
    # Active work stays tracked, but no longer belongs to a cell.
    assert executions.remove_cell(protocol.CellId("b")) == []
    assert executions.remove_cell(protocol.CellId("never")) == []
    assert executions.current(protocol.CellId("b")) is None
    complete(executions, "e2")
    done = executions.observe(
        be.Done(protocol.RunId("r1"), "succeeded"), RUNTIME
    )
    assert describe(done) == ["run r1", "execution.removed e2", "released r1"]


def test_restored_executions_are_current_until_replaced() -> None:
    document = Document([DocumentCell("c1", "42")], {})
    retained = dataclasses.replace(
        retained_execution(run_id="old-run"), variables=(variable("restored"),)
    )
    executions = Executions.restore(
        {protocol.CellId("c1"): retained}, cells=document
    )
    assert executions.current(protocol.CellId("c1")) == retained
    assert describe(executions._records()) == [
        "execution restored",
        "console restored-output",
        "variable v1",
    ]
    executions.begin(run("r1"), "request")
    changes = executions.observe(planned("r1", ("e1", "c1")), RUNTIME)
    assert describe(changes) == [
        "console.removed restored-output",
        "variable.removed v1",
        "execution.removed restored",
        "execution e1",
    ]
    assert executions.current(protocol.CellId("c1")) is None


@pytest.mark.parametrize(
    ("invalid", "message"),
    [
        ("scratch", "containing cell"),
        ("other-cell", "containing cell"),
        ("missing-cell", "not in the document"),
        ("unfinished", "completed"),
        ("output-owner", "belong to their execution"),
        ("duplicate-output", "unique"),
        ("variable-owner", "belong to their execution"),
        ("duplicate-item", "unique"),
    ],
)
def test_restore_rejects_inconsistent_executions(
    invalid: str, message: str
) -> None:
    document = Document([DocumentCell("c1", "42")], {})
    retained = retained_execution()
    execution, outputs = retained.execution, retained.outputs
    key = protocol.CellId("c1")
    if invalid == "scratch":
        retained = retained_execution(cell_id=None, run_id="previous-run")
    elif invalid == "other-cell":
        retained = CellExecution(
            replace(execution, cell_id=protocol.CellId("c2")), outputs
        )
    elif invalid == "missing-cell":
        key = protocol.CellId("missing")
        retained = CellExecution(replace(execution, cell_id=key), outputs)
    elif invalid == "unfinished":
        running = protocol.ExecutionRunning(started_at=utcnow())
        retained = CellExecution(replace(execution, state=running), outputs)
    elif invalid == "output-owner":
        retained = CellExecution(
            execution,
            (replace(outputs[0], execution_id=protocol.ExecutionId("other")),),
        )
    elif invalid == "variable-owner":
        retained = dataclasses.replace(
            retained, variables=(variable("other"),)
        )
    elif invalid == "duplicate-item":
        retained = dataclasses.replace(
            retained,
            variables=(replace(variable("restored"), id=outputs[0].id),),
        )
    else:
        retained = CellExecution(execution, outputs * 2)
    with pytest.raises(ValueError, match=message):
        Executions.restore({key: retained}, cells=document)


def test_current_result_keeps_its_outputs_as_the_execution_changes() -> None:
    executions = Executions()
    cell_id = protocol.CellId("a")
    assert executions.current(cell_id) is None
    executions.begin(run("r1"), "request")
    executions.observe(planned("r1", ("e1", "a")), RUNTIME)
    output = protocol.Console(
        execution_id=protocol.ExecutionId("e1"),
        id=protocol.ItemId("d1"),
        seq=0,
        content=protocol.ConsoleMedia(
            protocol.Media(mimetype="application/json", data='{"values":[1]}')
        ),
    )
    executions.observe(be.Produced(output), RUNTIME)
    assert executions.current(cell_id) is None
    complete(executions, "e1")
    result = executions.current(cell_id)
    assert result is not None
    assert result.outputs == (output,)

    updated = replace(
        output,
        content=protocol.ConsoleMedia(
            protocol.Media(
                mimetype="application/json", data='{"values":[1,2]}'
            )
        ),
    )
    executions.observe(be.Produced(updated), RUNTIME)
    current = executions.current(cell_id)
    assert current is not None
    assert current.outputs == (updated,)
    assert result.outputs == (output,)
