# Copyright 2026 Marimo. All rights reserved.
"""Run and execution transitions, without a stream or a backend."""

from __future__ import annotations

import pytest
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
from marimo._core.stream import kind_of, utcnow
from tests._core.conftest import retained_execution

NOTEBOOK = protocol.NotebookId("n1")
RUNTIME = protocol.Runtime(
    id=protocol.RuntimeId("rt-1"),
    notebook_id=NOTEBOOK,
    status="running",
    message=None,
    marimo_version=None,
    started_at=utcnow(),
)


def run(run_id: str) -> protocol.Run:
    return protocol.Run(
        id=protocol.RunId(run_id),
        notebook_id=NOTEBOOK,
        caused_by=None,
        status="queued",
        outcome=None,
        started_at=None,
        completed_at=None,
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
                "code" if cell is None else None,
            )
            for eid, cell in executions
        ),
    )


def complete(
    executions: Executions,
    eid: str,
    outcome: protocol.Outcome | None = None,
) -> list[Change]:
    execution = protocol.ExecutionId(eid)
    changes: list[Change] = []
    for msg in (
        be.Status(execution, "running"),
        be.Concluded(execution, outcome or protocol.ValueOutcome(None)),
        be.Status(execution, "completed"),
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
            out.append(f"{change.kind}.removed {change.id}")
        else:
            out.append(f"{kind_of(change)} {change.id}")
    return out


def test_a_cell_result_outlives_its_run_until_the_next_replaces_it() -> None:
    executions = Executions()
    executions.begin(run("r1"), "first")
    executions.observe(planned("r1", ("e1", "a")), RUNTIME)
    complete(executions, "e1")
    done = executions.observe(
        be.Done(protocol.RunId("r1"), "succeeded"), RUNTIME
    )
    assert describe(done) == ["run r1"]
    assert executions.active() is None
    assert describe(executions._records()) == ["run r1", "execution e1"]
    assert executions.request_id(protocol.RunId("r1")) == "first"
    assert executions.snapshot_request(protocol.RunId("r1")) is None

    executions.begin(run("r2"), "second")
    replaced = executions.observe(planned("r2", ("e2", "a")), RUNTIME)
    assert describe(replaced) == [
        "execution.removed e1",
        "released r1",
        "execution e2",
    ]
    executions.release(protocol.RunId("r1"))
    assert executions.run(protocol.RunId("r1")) is None
    assert describe(executions._records()) == ["run r2", "execution e2"]


def test_scratch_work_leaves_with_its_run() -> None:
    executions = Executions()
    executions.begin(run("r1"), "request")
    executions.observe(planned("r1", ("e1", None)), RUNTIME)
    produced = executions.observe(
        be.Produced(
            protocol.Console(
                protocol.ExecutionId("e1"),
                protocol.ItemId("c1"),
                "stdout",
                0,
                "x",
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


def test_a_run_completes_only_after_its_executions_and_reports_failures() -> (
    None
):
    executions = Executions()
    executions.begin(run("r1"), "request")
    executions.observe(planned("r1", ("e1", "a")), RUNTIME)
    executions.observe(
        be.Status(protocol.ExecutionId("e1"), "running"), RUNTIME
    )
    with pytest.raises(ValueError, match="unfinished"):
        executions.observe(be.Done(protocol.RunId("r1"), "succeeded"), RUNTIME)
    complete(executions, "e1", protocol.InterruptedOutcome())
    with pytest.raises(ValueError, match="successful"):
        executions.observe(be.Done(protocol.RunId("r1"), "succeeded"), RUNTIME)
    done = executions.observe(be.Done(protocol.RunId("r1"), "failed"), RUNTIME)
    assert [
        change.outcome for change in done if isinstance(change, protocol.Run)
    ] == ["failed"]


def test_interrupting_completes_everything_in_flight() -> None:
    executions = Executions()
    executions.begin(run("r1"), "request")
    executions.observe(planned("r1", ("e1", "a"), ("e2", None)), RUNTIME)
    for eid in ("e1", "e2"):
        executions.observe(
            be.Status(protocol.ExecutionId(eid), "running"), RUNTIME
        )
    changes = executions.interrupt()
    assert describe(changes) == ["execution e1", "execution e2", "run r1"]
    assert all(
        isinstance(change.outcome, protocol.InterruptedOutcome)
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
                protocol.ExecutionId("e1"),
                protocol.ItemId("c1"),
                "stdout",
                0,
                "x",
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
        executions.observe(be.Scheduled(protocol.RunId("r1")), None)
    assert (
        executions.observe(
            be.Status(protocol.ExecutionId("e1"), "running"), None
        )
        == []
    )
    scheduled = executions.observe(be.Scheduled(protocol.RunId("r1")), RUNTIME)
    assert describe(scheduled) == ["run r1"]
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
    executions.observe(
        be.Status(protocol.ExecutionId("e2"), "running"), RUNTIME
    )
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
    retained = retained_execution(run_id="old-run")
    executions = Executions.restore(
        {protocol.CellId("c1"): retained}, cells=document
    )
    assert executions.current(protocol.CellId("c1")) == retained
    assert describe(executions._records()) == [
        "execution restored",
        "console restored-output",
    ]
    executions.begin(run("r1"), "request")
    changes = executions.observe(planned("r1", ("e1", "c1")), RUNTIME)
    assert describe(changes) == [
        "console.removed restored-output",
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
        ("no-outcome", "outcome"),
        ("output-owner", "belong to their execution"),
        ("duplicate-output", "unique"),
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
        retained = CellExecution(replace(execution, status="running"), outputs)
    elif invalid == "no-outcome":
        retained = CellExecution(replace(execution, outcome=None), outputs)
    elif invalid == "output-owner":
        retained = CellExecution(
            execution,
            (replace(outputs[0], execution_id=protocol.ExecutionId("other")),),
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
    output = protocol.Display(
        execution_id=protocol.ExecutionId("e1"),
        id=protocol.ItemId("d1"),
        seq=0,
        mimetype="application/json",
        data='{"values":[1]}',
    )
    executions.observe(be.Produced(output), RUNTIME)
    assert executions.current(cell_id) is None
    complete(executions, "e1")
    result = executions.current(cell_id)
    assert result is not None
    assert result.outputs == (output,)

    updated = protocol.Display(
        execution_id=output.execution_id,
        id=output.id,
        seq=output.seq,
        mimetype=output.mimetype,
        data='{"values":[1,2]}',
    )
    executions.observe(be.Produced(updated), RUNTIME)
    current = executions.current(cell_id)
    assert current is not None
    assert current.outputs == (updated,)
    assert result.outputs[0].data == '{"values":[1]}'
