# Copyright 2026 Marimo. All rights reserved.
"""Retained run history for reconnecting clients."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import TYPE_CHECKING

from marimo._core import protocol, protocol_events
from marimo._core.stream import RoutedEvent, removal, snapshot_event

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class RetentionPolicy:
    """How long reconnecting clients can recover completed scratch runs."""

    ephemeral_seconds: float = 60.0

    def __post_init__(self) -> None:
        if not isfinite(self.ephemeral_seconds) or self.ephemeral_seconds < 0:
            raise ValueError("invalid result retention")


@dataclass
class _Scratch:
    """A scratch execution's latest event and its outputs."""

    execution: RoutedEvent
    outputs: dict[str, RoutedEvent] = field(default_factory=dict)


@dataclass
class _Run:
    """A run's latest event and what still keeps it visible."""

    event: RoutedEvent
    request_id: str | None
    live: set[str] = field(default_factory=set)
    scratch: dict[str, _Scratch] = field(default_factory=dict)
    completed_at: float | None = None
    had_executions: bool = False


class RunLog:
    """Run history for one notebook.

    Completed scratch results expire under the retention policy. A run
    remains while any visible execution refers to it. Runs that end before
    executing are retained for the same period as scratch results.

    A notebook releases completed scratch work without a removal event.
    The log keeps it until retention ends and publishes its removals.
    """

    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._runs: dict[str, _Run] = {}

    def observe(self, event: RoutedEvent) -> list[RoutedEvent]:
        """Record an event and return removals to publish after it."""
        match event.event:
            case protocol.RunEvent(
                data=protocol.RunMessage(run=run, request_id=request_id)
            ):
                entry = self._runs.get(run.id)
                if entry is None:
                    entry = self._runs[run.id] = _Run(
                        event,
                        request_id if isinstance(request_id, str) else None,
                    )
                entry.event = event
                if run.status == "completed" and entry.completed_at is None:
                    entry.completed_at = self._clock()
                return self._close(run.id)
            case protocol.ExecutionEvent(
                data=protocol.ExecutionMessage(execution=execution)
            ):
                if (entry := self._entry(event)) is not None:
                    entry.had_executions = True
                    entry.live.add(execution.id)
                    if execution.cell_id is None:
                        scratch = entry.scratch.get(execution.id)
                        if scratch is None:
                            entry.scratch[execution.id] = _Scratch(event)
                        else:
                            scratch.execution = event
            case protocol.ConsoleEvent(
                data=protocol.ConsoleMessage(console=item)
            ):
                self._record_output(event, item)
            case protocol.DisplayEvent(
                data=protocol.DisplayMessage(display=item)
            ):
                self._record_output(event, item)
            case protocol.ExecutionRemovedEvent(
                data=protocol.RemovedMessage(id=execution_id)
            ):
                if (entry := self._entry(event)) is not None:
                    entry.live.discard(execution_id)
                    entry.scratch.pop(execution_id, None)
                    assert event.run_id is not None
                    return self._close(event.run_id)
        return []

    def run(self, run_id: str) -> protocol.Run | None:
        """Return a retained run without reading its executions or outputs."""
        entry = self._runs.get(run_id)
        if entry is None:
            return None
        assert isinstance(entry.event.event, protocol.RunEvent)
        return entry.event.event.data.run

    def snapshot(self) -> list[RoutedEvent]:
        """Return the runs and scratch the log holds, parents first."""
        events = [
            self._snapshot_event(e.event, e) for e in self._runs.values()
        ]
        for entry in self._runs.values():
            for scratch in entry.scratch.values():
                events.append(self._snapshot_event(scratch.execution, entry))
                events.extend(
                    self._snapshot_event(output, entry)
                    for output in scratch.outputs.values()
                )
        return events

    def expire(self, policy: RetentionPolicy) -> list[RoutedEvent]:
        """Return removals for scratch whose retention has ended."""
        now = self._clock()
        events: list[RoutedEvent] = []
        for run_id, entry in list(self._runs.items()):
            if (
                (entry.scratch or not entry.had_executions)
                and entry.completed_at is not None
                and now >= entry.completed_at + policy.ephemeral_seconds
            ):
                events.extend(self._release(run_id))
        return events

    def clear(self) -> list[RoutedEvent]:
        """Remove all retained history."""
        events: list[RoutedEvent] = []
        for run_id, entry in list(self._runs.items()):
            entry.live.clear()
            if entry.completed_at is None:
                entry.completed_at = self._clock()
            events.extend(self._release(run_id))
        return events

    def _entry(self, event: RoutedEvent) -> _Run | None:
        return None if event.run_id is None else self._runs.get(event.run_id)

    def _record_output(
        self, event: RoutedEvent, item: protocol.Console | protocol.Display
    ) -> None:
        entry = self._entry(event)
        if entry is None:
            return
        scratch = entry.scratch.get(item.execution_id)
        if scratch is not None:
            scratch.outputs[item.id] = event

    def _release(self, run_id: str) -> list[RoutedEvent]:
        """Remove a run's scratch, then the run if nothing else holds it."""
        entry = self._runs[run_id]
        events: list[RoutedEvent] = []
        for execution_id, scratch in entry.scratch.items():
            for output in scratch.outputs.values():
                assert isinstance(
                    output.event,
                    (protocol.ConsoleEvent, protocol.DisplayEvent),
                )
                body = protocol_events.body(output.event)
                events.append(self._removal(entry, type(body), body.id))
            events.append(
                self._removal(entry, protocol.Execution, execution_id)
            )
            entry.live.discard(execution_id)
        entry.scratch.clear()
        return [*events, *self._close(run_id, retain_empty=False)]

    def _close(
        self, run_id: str, *, retain_empty: bool = True
    ) -> list[RoutedEvent]:
        entry = self._runs[run_id]
        if (
            entry.completed_at is None
            or entry.live
            or (retain_empty and not entry.had_executions)
        ):
            return []
        del self._runs[run_id]
        return [self._removal(entry, protocol.Run, run_id)]

    def _removal(
        self,
        entry: _Run,
        record_type: type[protocol_events.RemovableBody],
        object_id: str,
    ) -> RoutedEvent:
        return removal(
            record_type,
            object_id,
            notebook_id=entry.event.notebook_id,
            request_id=entry.request_id,
            run_id=entry.event.run_id,
        )

    def _snapshot_event(self, event: RoutedEvent, entry: _Run) -> RoutedEvent:
        assert isinstance(event.event, protocol_events.RecordEvent)
        body = protocol_events.body(event.event)
        assert isinstance(body, protocol_events.SnapshotBody)
        return snapshot_event(
            body,
            request_id=(
                None if entry.completed_at is not None else entry.request_id
            ),
            notebook_id=event.notebook_id,
            run_id=event.run_id,
        )
