# Copyright 2026 Marimo. All rights reserved.
"""Retained run history for reconnecting clients."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import TYPE_CHECKING

from marimo._core import protocol
from marimo._core.stream import Event, Kind, message, removal

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

    execution: Event
    outputs: dict[str, Event] = field(default_factory=dict)


@dataclass
class _Run:
    """A run's latest event and what still keeps it visible."""

    event: Event
    request_id: str | None
    live: set[str] = field(default_factory=set)
    scratch: dict[str, _Scratch] = field(default_factory=dict)
    completed_at: float | None = None


class RunLog:
    """Run history for one notebook.

    Completed scratch results expire under the retention policy. A run
    remains while any visible execution refers to it.
    """

    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._runs: dict[str, _Run] = {}

    def observe(self, event: Event) -> list[Event]:
        """Record an event and return any resulting removals."""
        match event:
            case Event(
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
            case Event(data=protocol.ExecutionMessage(execution=execution)):
                if (entry := self._entry(event)) is not None:
                    entry.live.add(execution.id)
                    if execution.cell_id is None:
                        scratch = entry.scratch.get(execution.id)
                        if scratch is None:
                            entry.scratch[execution.id] = _Scratch(event)
                        else:
                            scratch.execution = event
            case Event(data=protocol.ConsoleMessage(console=item)):
                self._record_output(event, item)
            case Event(data=protocol.DisplayMessage(display=item)):
                self._record_output(event, item)
            case Event(
                kind="execution", data=protocol.RemovedMessage(id=execution_id)
            ):
                if (entry := self._entry(event)) is not None:
                    entry.live.discard(execution_id)
                    entry.scratch.pop(execution_id, None)
                    assert event.run_id is not None
                    return self._close(event.run_id)
        return []

    def snapshot(self) -> list[Event]:
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

    def expire(self, policy: RetentionPolicy) -> list[Event]:
        """Return removals for scratch whose retention has ended."""
        now = self._clock()
        events: list[Event] = []
        for run_id, entry in list(self._runs.items()):
            if (
                entry.scratch
                and entry.completed_at is not None
                and now >= entry.completed_at + policy.ephemeral_seconds
            ):
                events.extend(self._release(run_id))
        return events

    def clear(self) -> list[Event]:
        """Remove all retained history."""
        events: list[Event] = []
        for run_id, entry in list(self._runs.items()):
            entry.live.clear()
            if entry.completed_at is None:
                entry.completed_at = self._clock()
            events.extend(self._release(run_id))
        return events

    def _entry(self, event: Event) -> _Run | None:
        return None if event.run_id is None else self._runs.get(event.run_id)

    def _record_output(
        self, event: Event, item: protocol.Console | protocol.Display
    ) -> None:
        entry = self._entry(event)
        if entry is None:
            return
        scratch = entry.scratch.get(item.execution_id)
        if scratch is not None:
            scratch.outputs[item.id] = event

    def _release(self, run_id: str) -> list[Event]:
        """Remove a run's scratch, then the run if nothing else holds it."""
        entry = self._runs[run_id]
        events: list[Event] = []
        for execution_id, scratch in entry.scratch.items():
            for output in scratch.outputs.values():
                assert output.kind is not None
                item = getattr(output.data, output.kind)
                events.append(self._removal(entry, output.kind, item.id))
            events.append(self._removal(entry, "execution", execution_id))
            entry.live.discard(execution_id)
        entry.scratch.clear()
        return [*events, *self._close(run_id)]

    def _close(self, run_id: str) -> list[Event]:
        entry = self._runs[run_id]
        if entry.completed_at is None or entry.live:
            return []
        del self._runs[run_id]
        return [self._removal(entry, "run", run_id)]

    def _removal(self, entry: _Run, kind: Kind, object_id: str) -> Event:
        return removal(
            kind,
            object_id,
            notebook_id=entry.event.notebook_id,
            request_id=entry.request_id,
            run_id=entry.event.run_id,
        )

    def _snapshot_event(self, event: Event, entry: _Run) -> Event:
        assert event.kind is not None
        body = getattr(event.data, event.kind)
        return Event(
            event.name,
            message(
                body,
                request_id=(
                    None
                    if entry.completed_at is not None
                    else entry.request_id
                ),
            ),
            notebook_id=event.notebook_id,
            run_id=event.run_id,
        )
