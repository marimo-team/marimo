# Copyright 2026 Marimo. All rights reserved.
"""Runs, cell results, and their outputs."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from msgspec.structs import replace

from marimo._core import backend as be, protocol
from marimo._core.errors import NoRuntime
from marimo._core.stream import utcnow

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


@dataclass(frozen=True)
class CellExecution:
    """A completed cell execution with its console and display outputs.

    Its source may be older than the cell's current source.
    """

    execution: protocol.Execution
    outputs: tuple[protocol.Console | protocol.Display, ...] = ()


@dataclass
class _Run:
    """A run in progress or retained by a cell result."""

    run: protocol.Run
    request_id: str | None = None
    executions: set[protocol.ExecutionId] = field(default_factory=set)
    # Cell executions replaced while the run was in progress, and whether
    # each succeeded. A successful run cannot have replaced a failure.
    retired: dict[protocol.ExecutionId, bool] = field(default_factory=dict)


@dataclass
class _Result:
    """A current execution and its outputs."""

    execution: protocol.Execution
    outputs: dict[protocol.ItemId, protocol.Console | protocol.Display] = (
        field(default_factory=dict)
    )


@dataclass(frozen=True)
class Removed:
    """A current record that a transition removed."""

    kind: Literal["execution", "console", "display", "variable"]
    id: str
    run_id: protocol.RunId | None


@dataclass(frozen=True)
class Released:
    """A run to release after applying its preceding changes.

    Releasing emits no event. Earlier changes still use the run's request ID.
    """

    run_id: protocol.RunId


Record = (
    protocol.Run | protocol.Execution | protocol.Console | protocol.Display
)
Change = Record | Removed | Released


class Executions:
    """Runs in progress and each cell's current result.

    Cell results remain until replaced or removed. Scratch executions
    leave when their run completes.
    """

    def __init__(self) -> None:
        self._runs: dict[protocol.RunId, _Run] = {}
        self._results: dict[protocol.ExecutionId, _Result] = {}
        self._cells: dict[protocol.CellId, protocol.ExecutionId] = {}

    @classmethod
    def restore(
        cls,
        executions: Mapping[protocol.CellId, CellExecution],
        *,
        cells: Iterable[protocol.Cell],
    ) -> Executions:
        """Restore completed executions for cells in the document.

        Execution and output IDs must be unique. Each output must belong
        to its containing execution.
        """
        known = {cell.id for cell in cells}
        restored = cls()
        output_ids: set[protocol.ItemId] = set()
        for cell_id, retained in deepcopy(dict(executions)).items():
            execution = retained.execution
            if execution.cell_id != cell_id:
                raise ValueError(
                    "results must belong to their containing cell"
                )
            if cell_id not in known:
                raise ValueError(
                    f"result for cell {cell_id} not in the document"
                )
            outputs = sorted(retained.outputs, key=lambda item: item.seq)
            if execution.status != "completed":
                raise ValueError(
                    "initial results must be completed executions"
                )
            if execution.outcome is None:
                raise ValueError("initial results must have an outcome")
            if execution.id in restored._results:
                raise ValueError("initial execution ids must be unique")
            if any(item.execution_id != execution.id for item in outputs):
                raise ValueError(
                    "result outputs must belong to their execution"
                )
            if len({item.id for item in outputs}) != len(outputs):
                raise ValueError("result output ids must be unique")
            if output_ids.intersection(item.id for item in outputs):
                raise ValueError(
                    "result output ids must be unique across cells"
                )
            output_ids.update(item.id for item in outputs)
            restored._results[execution.id] = _Result(
                execution, {item.id: item for item in outputs}
            )
            restored._cells[cell_id] = execution.id
        return restored

    # ---- reads ---------------------------------------------------------

    def current(self, cell_id: protocol.CellId) -> CellExecution | None:
        """A copy of the cell's completed result, or `None` while it runs."""
        execution_id = self._cells.get(cell_id)
        current = (
            self._results.get(execution_id)
            if execution_id is not None
            else None
        )
        if current is None or current.execution.status != "completed":
            return None
        return deepcopy(
            CellExecution(current.execution, tuple(current.outputs.values()))
        )

    def run(self, run_id: protocol.RunId) -> protocol.Run | None:
        tracked = self._runs.get(run_id)
        return tracked.run if tracked is not None else None

    def active(self) -> protocol.Run | None:
        """The run in progress, if any."""
        return next(
            (
                tracked.run
                for tracked in self._runs.values()
                if tracked.run.status != "completed"
            ),
            None,
        )

    def _records(self) -> list[Record]:
        """Return detached current records, including unfinished executions."""
        return deepcopy(
            [
                *(tracked.run for tracked in self._runs.values()),
                *(result.execution for result in self._results.values()),
                *(
                    item
                    for result in self._results.values()
                    for item in result.outputs.values()
                ),
            ]
        )

    def run_id_of(self, change: Record | Removed) -> protocol.RunId | None:
        """Resolve a record or removal to the run it belongs to."""
        if isinstance(change, protocol.Run):
            return change.id
        if isinstance(change, (protocol.Execution, Removed)):
            return change.run_id
        return self._results[change.execution_id].execution.run_id

    def request_id(self, run_id: protocol.RunId | None) -> str | None:
        """The request behind a run still tracked."""
        tracked = self._runs.get(run_id) if run_id is not None else None
        return tracked.request_id if tracked is not None else None

    def snapshot_request(self, run_id: protocol.RunId | None) -> str | None:
        """The request behind a run still in progress."""
        tracked = self._runs.get(run_id) if run_id is not None else None
        if tracked is not None and tracked.run.status != "completed":
            return tracked.request_id
        return None

    # ---- transitions ---------------------------------------------------

    def begin(self, run: protocol.Run, request_id: str) -> list[Change]:
        """Track a run the notebook requested."""
        self._runs[run.id] = _Run(run, request_id)
        return [run]

    def release(self, run_id: protocol.RunId) -> None:
        """Stop tracking a released run."""
        del self._runs[run_id]

    def remove_cell(self, cell_id: protocol.CellId) -> list[Change]:
        """Remove a deleted cell's result.

        An active execution stays until its run completes.
        """
        execution_id = self._cells.get(cell_id)
        if execution_id is None:
            return []
        if self._results[execution_id].execution.status == "completed":
            return self._retire_execution(execution_id)
        self._cells.pop(cell_id)
        return []

    def observe(
        self, msg: be.Message, runtime: protocol.Runtime | None
    ) -> list[Change]:
        """Apply a backend update and return its changes in publication order."""
        changes: list[Change] = []
        match msg:
            case be.Scheduled(run_id=run_id, caused_by=caused_by):
                if run_id not in self._runs:
                    runtime = self._require(runtime)
                    changes.append(
                        self._set_run(
                            protocol.Run(
                                id=run_id,
                                notebook_id=runtime.notebook_id,
                                caused_by=caused_by,
                                status="queued",
                                outcome=None,
                                started_at=None,
                                completed_at=None,
                            )
                        )
                    )
            case be.Planned(run_id=run_id, executions=planned):
                changes.extend(self._observe_planned(run_id, planned, runtime))
            case be.Status(execution_id=execution_id, status=status):
                changes.extend(self._observe_status(execution_id, status))
            case be.Produced(item=item):
                if (
                    result := self._results.get(item.execution_id)
                ) is not None:
                    result.outputs[item.id] = item
                    changes.append(item)
            case be.Concluded(execution_id=execution_id, outcome=outcome):
                if (
                    result := self._results.get(execution_id)
                ) is not None and result.execution.status != "completed":
                    changes.append(
                        self._set_execution(
                            replace(result.execution, outcome=outcome)
                        )
                    )
            case be.Done(run_id=run_id, outcome=outcome):
                if (
                    tracked := self._runs.get(run_id)
                ) is not None and tracked.run.status != "completed":
                    members = [
                        self._results[eid].execution
                        for eid in tracked.executions
                    ]
                    if any(
                        execution.status != "completed"
                        for execution in members
                    ):
                        raise ValueError(
                            "a run cannot complete with unfinished executions"
                        )
                    if outcome == "succeeded" and (
                        not all(tracked.retired.values())
                        or any(
                            not isinstance(
                                execution.outcome, protocol.ValueOutcome
                            )
                            for execution in members
                        )
                    ):
                        raise ValueError(
                            "a successful run cannot contain failed or interrupted executions"
                        )
                    changes.append(
                        self._set_run(
                            replace(
                                tracked.run,
                                status="completed",
                                outcome=outcome,
                                completed_at=utcnow(),
                            )
                        )
                    )
                    tracked.retired.clear()
                    changes.extend(self._finish_run(tracked))
        return changes

    def interrupt(
        self, outcome: protocol.RunOutcome = "interrupted"
    ) -> list[Change]:
        """Complete every unfinished execution and run."""
        changes: list[Change] = []
        now = utcnow()
        for result in list(self._results.values()):
            if result.execution.status != "completed":
                changes.append(
                    self._set_execution(
                        replace(
                            result.execution,
                            status="completed",
                            outcome=protocol.InterruptedOutcome(),
                            completed_at=now,
                        )
                    )
                )
        for tracked in list(self._runs.values()):
            if tracked.run.status != "completed":
                changes.append(
                    self._set_run(
                        replace(
                            tracked.run,
                            status="completed",
                            outcome=outcome,
                            completed_at=now,
                        )
                    )
                )
            tracked.retired.clear()
            changes.extend(self._finish_run(tracked))
        return changes

    def clear(self) -> list[Change]:
        """Remove every current execution and release every run."""
        changes: list[Change] = []
        for execution_id in list(self._results):
            changes.extend(self._remove_execution(execution_id))
        changes.extend(Released(run_id) for run_id in self._runs)
        return changes

    # ---- internals -----------------------------------------------------

    @staticmethod
    def _require(runtime: protocol.Runtime | None) -> protocol.Runtime:
        if runtime is None:
            raise NoRuntime("the notebook has no runtime; start one first.")
        return runtime

    def _observe_planned(
        self,
        run_id: protocol.RunId,
        planned: tuple[be.PlannedExecution, ...],
        runtime: protocol.Runtime | None,
    ) -> list[Change]:
        changes: list[Change] = []
        if (
            tracked := self._runs.get(run_id)
        ) is None or tracked.run.status == "completed":
            return []
        runtime = self._require(runtime)
        for entry in planned:
            if entry.id in self._results or entry.id in tracked.retired:
                continue
            if entry.cell_id is not None:
                previous = self._cells.get(protocol.CellId(entry.cell_id))
                if previous is not None:
                    changes.extend(self._retire_execution(previous))
            changes.append(
                self._set_execution(
                    protocol.Execution(
                        id=entry.id,
                        run_id=run_id,
                        runtime_id=runtime.id,
                        caused_by=entry.caused_by,
                        cell_id=protocol.CellId(entry.cell_id)
                        if entry.cell_id is not None
                        else None,
                        code=entry.code,
                        code_hash=entry.code_hash,
                        status="queued",
                        outcome=None,
                        stale=None,
                        started_at=None,
                        completed_at=None,
                    )
                )
            )
        return changes

    def _observe_status(
        self, execution_id: protocol.ExecutionId, status: protocol.Lifecycle
    ) -> list[Change]:
        changes: list[Change] = []
        result = self._results.get(execution_id)
        if result is None:
            return []
        execution = result.execution
        if execution.status in (status, "completed"):
            return []
        now = utcnow()
        if status == "running":
            execution = replace(execution, status=status, started_at=now)
            assert execution.run_id is not None
            run = self._runs[execution.run_id].run
            if run.status == "queued":
                changes.append(
                    self._set_run(
                        replace(run, status="running", started_at=now)
                    )
                )
        elif status == "completed":
            if execution.outcome is None:
                raise ValueError("a completed execution must have an outcome")
            execution = replace(execution, status=status, completed_at=now)
        else:
            execution = replace(execution, status=status)
        changes.append(self._set_execution(execution))
        return changes

    def _set_run(self, run: protocol.Run) -> protocol.Run:
        self._runs.setdefault(run.id, _Run(run)).run = run
        return run

    def _set_execution(
        self, execution: protocol.Execution
    ) -> protocol.Execution:
        result = self._results.get(execution.id)
        if result is None:
            self._results[execution.id] = _Result(execution)
            if execution.cell_id is not None:
                self._cells[execution.cell_id] = execution.id
        else:
            result.execution = execution
        if execution.run_id is not None:
            if (tracked := self._runs.get(execution.run_id)) is not None:
                tracked.executions.add(execution.id)
        return execution

    def _finish_run(self, tracked: _Run) -> list[Change]:
        """Release completed work that no cell retains."""
        changes: list[Change] = []
        for execution_id in list(tracked.executions):
            execution = self._results[execution_id].execution
            if execution.cell_id is None:
                self._forget_result(execution_id)
            elif self._cells.get(execution.cell_id) != execution_id:
                changes.extend(self._remove_execution(execution_id))
        changes.extend(self._prune_run(tracked))
        return changes

    def _prune_run(self, tracked: _Run) -> list[Released]:
        if tracked.run.status != "completed" or tracked.executions:
            return []
        return [Released(tracked.run.id)]

    def _retire_execution(
        self, execution_id: protocol.ExecutionId
    ) -> list[Change]:
        """Replace a cell's current execution with a newer one."""
        execution = self._results[execution_id].execution
        if execution.status != "completed":
            raise ValueError("cannot replace an unfinished cell execution")
        tracked = (
            self._runs.get(execution.run_id)
            if execution.run_id is not None
            else None
        )
        if tracked is not None and tracked.run.status != "completed":
            tracked.retired[execution.id] = isinstance(
                execution.outcome, protocol.ValueOutcome
            )
        changes: list[Change] = list(self._remove_execution(execution_id))
        if tracked is not None:
            changes.extend(self._prune_run(tracked))
        return changes

    def _remove_execution(
        self, execution_id: protocol.ExecutionId
    ) -> list[Removed]:
        """Remove an execution and its outputs, outputs first."""
        result = self._results[execution_id]
        run_id = result.execution.run_id
        changes: list[Removed] = [
            Removed(
                "console" if isinstance(item, protocol.Console) else "display",
                item.id,
                run_id,
            )
            for item in result.outputs.values()
        ]
        changes.append(Removed("execution", execution_id, run_id))
        self._forget_result(execution_id)
        return changes

    def _forget_result(self, execution_id: protocol.ExecutionId) -> None:
        result = self._results.pop(execution_id)
        if (
            result.execution.cell_id is not None
            and self._cells.get(result.execution.cell_id) == execution_id
        ):
            del self._cells[result.execution.cell_id]
        if result.execution.run_id is not None:
            if (
                tracked := self._runs.get(result.execution.run_id)
            ) is not None:
                tracked.executions.discard(execution_id)
