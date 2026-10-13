# Copyright 2026 Marimo. All rights reserved.
"""Execution state for connecting and reconnecting clients.

Reconnecting clients replay past events, so events are retained.
Retaining all of them is impractical. `ExecutionState` applies the
host's retention policy and emits removal events so connected clients
can update their snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import TYPE_CHECKING

from msgspec.structs import replace

from marimo._core import backend as be, protocol
from marimo._core.errors import NoRuntime
from marimo._core.stream import Event, Stream, kind_of, message, utcnow

if TYPE_CHECKING:
    from collections.abc import Callable

Item = protocol.Console | protocol.Display


@dataclass
class _RetainedExecution:
    """An execution with the outputs it produced."""

    execution: protocol.Execution
    outputs: dict[protocol.ItemId, Item] = field(default_factory=dict)


@dataclass(frozen=True)
class RetentionPolicy:
    """How long the host retains ephemeral results after a run completes."""

    ephemeral_seconds: float = 60.0

    def __post_init__(self) -> None:
        if not isfinite(self.ephemeral_seconds) or self.ephemeral_seconds < 0:
            raise ValueError("invalid result retention")


class ExecutionState:
    """Retain current results and remove completed runs with no executions."""

    def __init__(
        self,
        notebook_id: protocol.NotebookId,
        stream: Stream,
        retention: RetentionPolicy,
        clock: Callable[[], float],
        forget: Callable[[protocol.RunId], None],
    ) -> None:
        self._id = notebook_id
        self._stream = stream
        self._retention = retention
        self._clock = clock
        self._forget = forget
        self._runs: dict[str, protocol.Run] = {}
        self._run_executions: dict[str, set[protocol.ExecutionId]] = {}
        self._run_requests: dict[str, str | None] = {}
        self._executions: dict[protocol.ExecutionId, _RetainedExecution] = {}
        self._cell_executions: dict[protocol.CellId, protocol.ExecutionId] = {}
        self._retired_executions: dict[
            protocol.ExecutionId, protocol.RunId
        ] = {}
        self._unsuccessful: set[protocol.RunId] = set()
        self._completed_at: dict[str, float] = {}

    @property
    def id(self) -> protocol.NotebookId:
        return self._id

    @property
    def active_run(self) -> protocol.Run | None:
        return next(
            (r for r in self._runs.values() if r.status != "completed"), None
        )

    def run(self, run_id: str) -> protocol.Run | None:
        return self._runs.get(run_id)

    def add_run(self, run: protocol.Run, request_id: str) -> None:
        self._run_requests[run.id] = request_id
        self._set_run(run)

    def expire(self) -> None:
        now = self._clock()
        for retained in list(self._executions.values()):
            execution = retained.execution
            ended = self._completed_at.get(execution.run_id or "")
            if (
                execution.cell_id is None
                and ended is not None
                and now >= ended + self._retention.ephemeral_seconds
            ):
                self._retire_execution(retained)

    def _prune_run(self, run_id: str | None) -> None:
        run = self._runs.get(run_id or "")
        if run is None or run.status != "completed":
            return
        if self._run_executions[run.id]:
            return
        del self._runs[run.id]
        del self._run_executions[run.id]
        self._remove("run", run.id, run.id)
        self._run_requests.pop(run.id, None)
        self._completed_at.pop(run.id, None)
        self._forget(run.id)

    def snapshot(self) -> list[Event]:
        bodies: list[protocol.Run | protocol.Execution | Item] = [
            *self._runs.values(),
            *(retained.execution for retained in self._executions.values()),
            *(
                item
                for retained in self._executions.values()
                for item in retained.outputs.values()
            ),
        ]
        return [
            Event(
                kind_of(body),
                message(body, request_id=self._pending_request(body)),
                notebook_id=self.id,
                run_id=self._run_id(body),
            )
            for body in bodies
        ]

    def _pending_request(
        self, body: protocol.Run | protocol.Execution | Item
    ) -> str | None:
        run_id = self._run_id(body)
        run = self._runs.get(run_id or "")
        return (
            self._run_requests.get(run.id)
            if run is not None and run.status != "completed"
            else None
        )

    def observe(
        self, msg: be.Message, runtime: protocol.Runtime | None
    ) -> None:
        match msg:
            case be.Scheduled(run_id=run_id, caused_by=caused_by):
                if run_id not in self._runs:
                    if runtime is None:
                        raise NoRuntime(f"notebook {self.id} has no runtime")
                    self._run_requests[run_id] = None
                    self._set_run(
                        protocol.Run(
                            id=run_id,
                            notebook_id=self.id,
                            caused_by=caused_by,
                            status="queued",
                            outcome=None,
                            started_at=None,
                            completed_at=None,
                        )
                    )
            case be.Planned(run_id=run_id, executions=planned):
                self._observe_planned(run_id, planned, runtime)
            case be.Status(execution_id=execution_id, status=status):
                self._observe_status(execution_id, status)
            case be.Produced(item=item):
                if (
                    retained := self._executions.get(item.execution_id)
                ) is not None:
                    retained.outputs[item.id] = item
                    self._publish(item)
            case be.Concluded(execution_id=execution_id, outcome=outcome):
                if (
                    retained := self._executions.get(execution_id)
                ) is not None and retained.execution.status != "completed":
                    self._set_execution(
                        replace(retained.execution, outcome=outcome)
                    )
            case be.Done(run_id=run_id, outcome=outcome):
                if (
                    run := self._runs.get(run_id)
                ) is not None and run.status != "completed":
                    members = [
                        self._executions[eid].execution
                        for eid in self._run_executions[run_id]
                    ]
                    if any(
                        execution.status != "completed"
                        for execution in members
                    ):
                        raise ValueError(
                            "a run cannot complete with unfinished executions"
                        )
                    if outcome == "succeeded" and (
                        run_id in self._unsuccessful
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
                    self._set_run(
                        replace(
                            run,
                            status="completed",
                            outcome=outcome,
                            completed_at=utcnow(),
                        )
                    )
                    self._retired_executions = {
                        eid: rid
                        for eid, rid in self._retired_executions.items()
                        if rid != run_id
                    }
                    self._unsuccessful.discard(run_id)

                    self._prune_run(run_id)

    def clear(self) -> None:
        self._retired_executions.clear()
        self._unsuccessful.clear()
        for retained in list(self._executions.values()):
            self._remove_execution(retained)
        for run in list(self._runs.values()):
            del self._runs[run.id]
            del self._run_executions[run.id]
            self._remove("run", run.id, run.id)
            self._run_requests.pop(run.id, None)
            self._forget(run.id)
        self._completed_at.clear()

    def _set_run(self, run: protocol.Run) -> None:
        self._runs[run.id] = run
        self._run_executions.setdefault(run.id, set())
        if run.status == "completed":
            self._completed_at.setdefault(run.id, self._clock())
        self._publish(run)

    def _set_execution(self, execution: protocol.Execution) -> None:
        if (retained := self._executions.get(execution.id)) is None:
            self._executions[execution.id] = _RetainedExecution(execution)
        else:
            retained.execution = execution
        if execution.cell_id is not None:
            self._cell_executions[execution.cell_id] = execution.id
        if execution.run_id is not None:
            self._run_executions[execution.run_id].add(execution.id)
        self._publish(execution)

    def interrupt(self, outcome: protocol.RunOutcome = "interrupted") -> None:
        now = utcnow()
        for retained in list(self._executions.values()):
            execution = retained.execution
            if execution.status != "completed":
                self._set_execution(
                    replace(
                        execution,
                        status="completed",
                        outcome=protocol.InterruptedOutcome(),
                        completed_at=now,
                    )
                )
        for run in list(self._runs.values()):
            if run.status != "completed":
                self._set_run(
                    replace(
                        run,
                        status="completed",
                        outcome=outcome,
                        completed_at=now,
                    )
                )
        self._retired_executions.clear()
        self._unsuccessful.clear()

        for run_id in list(self._runs):
            self._prune_run(run_id)

    def _observe_planned(
        self,
        run_id: protocol.RunId,
        planned: tuple[be.PlannedExecution, ...],
        runtime: protocol.Runtime | None,
    ) -> None:
        if (
            run := self._runs.get(run_id)
        ) is None or run.status == "completed":
            return
        if runtime is None:
            raise NoRuntime(f"notebook {self.id} has no runtime")
        for entry in planned:
            if (
                entry.id in self._executions
                or entry.id in self._retired_executions
            ):
                continue
            if entry.cell_id is not None:
                previous = self._cell_executions.get(
                    protocol.CellId(entry.cell_id)
                )
                if previous is not None:
                    self._retire_execution(self._executions[previous])
            self._set_execution(
                protocol.Execution(
                    id=entry.id,
                    run_id=run_id,
                    runtime_id=runtime.id,
                    caused_by=entry.caused_by,
                    cell_id=(
                        protocol.CellId(entry.cell_id)
                        if entry.cell_id is not None
                        else None
                    ),
                    code=entry.code,
                    code_hash=entry.code_hash,
                    bindings=(),
                    status="queued",
                    outcome=None,
                    stale=None,
                    started_at=None,
                    completed_at=None,
                )
            )

    def _retire_execution(self, retained: _RetainedExecution) -> None:
        execution = retained.execution
        if execution.status != "completed":
            raise ValueError("cannot replace an unfinished cell execution")
        run_id = execution.run_id
        run = self._runs.get(run_id) if run_id is not None else None
        if run is not None and run.status != "completed":
            self._retired_executions[execution.id] = run.id
            if not isinstance(execution.outcome, protocol.ValueOutcome):
                self._unsuccessful.add(run.id)
        self._remove_execution(retained)
        self._prune_run(run_id)

    def _remove_execution(self, retained: _RetainedExecution) -> None:
        execution = retained.execution
        run_id = execution.run_id
        for item in list(retained.outputs.values()):
            del retained.outputs[item.id]
            self._remove(kind_of(item), item.id, run_id)
        del self._executions[execution.id]
        if execution.cell_id is not None:
            del self._cell_executions[execution.cell_id]
        if run_id is not None:
            self._run_executions[run_id].remove(execution.id)
        self._remove("execution", execution.id, run_id)

    def _observe_status(
        self, execution_id: protocol.ExecutionId, status: protocol.Lifecycle
    ) -> None:
        retained = self._executions.get(execution_id)
        if retained is None:
            return
        execution = retained.execution
        if execution.status in (status, "completed"):
            return
        now = utcnow()
        if status == "running":
            execution = replace(execution, status=status, started_at=now)
            assert execution.run_id is not None
            run = self._runs[execution.run_id]
            if run.status == "queued":
                self._set_run(replace(run, status="running", started_at=now))
        elif status == "completed":
            if execution.outcome is None:
                raise ValueError("a completed execution must have an outcome")
            execution = replace(execution, status=status, completed_at=now)
        else:
            execution = replace(execution, status=status)
        self._set_execution(execution)

    def _publish(
        self,
        body: protocol.Run | protocol.Execution | Item,
    ) -> None:
        run_id = self._run_id(body)
        self._stream.publish(
            body,
            notebook_id=self.id,
            request_id=self._run_requests.get(run_id or ""),
            run_id=run_id,
        )

    def _run_id(
        self,
        body: protocol.Run | protocol.Execution | Item,
    ) -> protocol.RunId | None:
        if isinstance(body, protocol.Run):
            return body.id
        if isinstance(body, protocol.Execution):
            return body.run_id
        if isinstance(body, (protocol.Console, protocol.Display)):
            return self._executions[body.execution_id].execution.run_id
        return None

    def _remove(
        self,
        kind: str,
        object_id: str,
        run_id: protocol.RunId | None,
    ) -> None:
        self._stream.remove(
            kind,
            object_id,
            notebook_id=self.id,
            request_id=self._run_requests.get(run_id or ""),
            run_id=run_id,
        )
