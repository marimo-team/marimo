# Copyright 2026 Marimo. All rights reserved.
"""Projects, notebooks, and event subscriptions for a marimo host."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING

from marimo._core import protocol, protocol_events
from marimo._core.errors import NotFound
from marimo._core.notebook import Notebook
from marimo._core.run_log import RetentionPolicy, RunLog
from marimo._core.stream import (
    Listener,
    RoutedEvent,
    Sink,
    Stream,
    snapshot_event,
)

if TYPE_CHECKING:
    from collections.abc import Collection, Iterator, Sequence
    from contextlib import AbstractContextManager

    from marimo._core.protocol_events import Body


NotebookInitializer = Callable[
    [protocol.Notebook, Sink], Notebook | Awaitable[Notebook]
]


@dataclass
class _NotebookEntry:
    """A catalog entry, its run history, and the notebook once loaded."""

    initialize: NotebookInitializer
    log: RunLog
    notebook: Notebook | None = None
    task: asyncio.Task[Notebook] | None = None
    sink: _NotebookSink | None = None


class _NotebookSink(Sink):
    """A notebook's sink: the run log sees each event, then the stream."""

    def __init__(self, stream: Stream, log: RunLog) -> None:
        self._stream = stream
        self._log = log
        # Publish initial state only after the host accepts the notebook.
        self.active = False

    def deferred(self) -> AbstractContextManager[None]:
        return self._stream.deferred()

    def _append(self, event: RoutedEvent) -> RoutedEvent:
        if not self.active:
            return event
        with self._stream.deferred():
            removals = self._log.observe(event)
            recorded = self._stream._append(event)
            for removed in removals:
                self._stream._append(removed)
        return recorded


class _NotebookRecords(Mapping[str, protocol.Notebook]):
    """Catalog records copied on read."""

    def __init__(self, records: Mapping[str, protocol.Notebook]) -> None:
        self._records = records

    def __getitem__(self, key: str) -> protocol.Notebook:
        return deepcopy(self._records[key])

    def __iter__(self) -> Iterator[str]:
        return iter(self._records)

    def __len__(self) -> int:
        return len(self._records)


def _identity(event: RoutedEvent) -> tuple[type[Body], str]:
    assert isinstance(event.event, protocol_events.RecordEvent)
    body = protocol_events.body(event.event)
    assert not isinstance(body, (protocol.Host, protocol.Custom))
    if isinstance(body, (protocol.Document, protocol.Analysis)):
        return type(body), body.notebook_id
    return type(body), body.id


class Host:
    """A host's project and notebook catalog, with events for changes."""

    def __init__(
        self,
        *,
        operations: Sequence[str],
        history: int = 1000,
        retention: RetentionPolicy | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.retention = retention or RetentionPolicy()
        self.clock = clock
        self._host = protocol.Host(operations=tuple(operations))
        self._stream = Stream(history=history)
        # Lookups accept wire strings; stored objects carry branded IDs.
        self._projects: dict[str, protocol.Project] = {}
        self._records: dict[str, protocol.Notebook] = {}
        self._entries: dict[str, _NotebookEntry] = {}

    @property
    def notebooks(self) -> Mapping[str, protocol.Notebook]:
        """Catalog metadata, independent of each notebook's execution state."""
        return _NotebookRecords(self._records)

    @property
    def operations(self) -> list[str]:
        return list(self._host.operations)

    def update_project(
        self, project: protocol.Project, *, request_id: str | None = None
    ) -> None:
        """Store a project and publish an event if it changed."""
        if self._projects.get(project.id) == project:
            return
        self._projects[project.id] = deepcopy(project)
        self._stream.publish(project, request_id=request_id)

    def add_notebook(
        self,
        record: protocol.Notebook,
        initialize: NotebookInitializer,
        *,
        request_id: str | None = None,
    ) -> None:
        """Register a notebook with its initializer."""
        if record.id in self._records:
            raise ValueError(f"notebook {record.id} is already in the catalog")
        if record.project_id not in self._projects:
            raise ValueError(
                f"project {record.project_id} is not in the catalog"
            )
        self._records[record.id] = deepcopy(record)
        self._entries[record.id] = _NotebookEntry(
            initialize, RunLog(lambda: self.clock())
        )
        self._stream.publish(
            record, notebook_id=record.id, request_id=request_id
        )

    def update_notebook(
        self, record: protocol.Notebook, *, request_id: str | None = None
    ) -> None:
        """Update catalog metadata without changing the notebook's state."""
        if record.id not in self._records:
            raise NotFound(f"no notebook {record.id}")
        if record.project_id not in self._projects:
            raise ValueError(
                f"project {record.project_id} is not in the catalog"
            )
        if self._records[record.id] == record:
            return
        self._records[record.id] = deepcopy(record)
        self._stream.publish(
            record, notebook_id=record.id, request_id=request_id
        )

    def remove_notebook(
        self, notebook_id: str, *, request_id: str | None = None
    ) -> None:
        """Remove a notebook, its runtime, attachments, and runs."""
        record = self._records.pop(notebook_id, None)
        if record is None:
            return
        entry = self._entries.pop(notebook_id)
        if entry.task is not None:
            entry.task.cancel()

        with self._stream.deferred():
            if entry.notebook is not None:
                entry.notebook._dispose(request_id=request_id)
            for event in entry.log.clear():
                self._stream.append(event)
            if entry.sink is not None:
                entry.sink.active = False
            self._stream.remove(
                protocol.Notebook,
                record.id,
                notebook_id=record.id,
                request_id=request_id,
            )

    async def notebook(self, notebook_id: str) -> Notebook:
        """Load a notebook on first access.

        Concurrent callers share initialization. Failed loads can be retried.
        Cancelling a caller leaves shared loading intact.
        """
        entry = self._entries.get(notebook_id)
        if entry is None:
            raise NotFound(f"no notebook {notebook_id}")
        if entry.notebook is not None:
            return entry.notebook
        if entry.task is None:
            entry.task = asyncio.create_task(
                self._initialize(notebook_id, entry)
            )
        try:
            return await asyncio.shield(entry.task)
        except asyncio.CancelledError:
            if self._entries.get(notebook_id) is not entry:
                raise NotFound(f"no notebook {notebook_id}") from None
            raise

    def peek_notebook(self, notebook_id: str) -> Notebook | None:
        """Return the notebook if loaded without initializing it."""
        entry = self._entries.get(notebook_id)
        if entry is None:
            raise NotFound(f"no notebook {notebook_id}")
        return entry.notebook

    async def _initialize(
        self, notebook_id: str, entry: _NotebookEntry
    ) -> Notebook:
        try:
            sink = _NotebookSink(self._stream, entry.log)
            result = entry.initialize(
                deepcopy(self._records[notebook_id]), sink
            )
            notebook = await result if inspect.isawaitable(result) else result
            if self._entries.get(notebook_id) is not entry:
                raise NotFound(f"no notebook {notebook_id}")
            if notebook.id != notebook_id:
                raise ValueError(
                    "initialized notebook must match its catalog id"
                )
            entry.notebook = notebook

            entry.sink = sink
            sink.active = True
            # The initial state joins the stream the way later changes do,
            # so the run history sees every run from its first event.
            with self._stream.deferred():
                for body, run_id in notebook._records():
                    sink.publish(
                        body,
                        notebook_id=notebook.id,
                        run_id=run_id,
                    )
            if self._entries.get(notebook_id) is not entry:
                raise NotFound(f"no notebook {notebook_id}")
            return notebook
        finally:
            entry.task = None

    def run(self, notebook_id: str, run_id: str) -> protocol.Run | None:
        """Return a run the host still retains, if any."""
        entry = self._entries.get(notebook_id)
        if entry is None:
            raise NotFound(f"no notebook {notebook_id}")
        return entry.log.run(run_id)

    def _snapshot(
        self, notebook_id: protocol.NotebookId | None = None
    ) -> list[RoutedEvent]:
        """Return catalog or notebook state with retained run history."""
        if notebook_id is not None:
            records = [self._records[notebook_id]]
            events: list[RoutedEvent] = []
        else:
            records = list(self._records.values())
            events = [snapshot_event(self._host)]
            events.extend(snapshot_event(p) for p in self._projects.values())
        for record in records:
            events.append(snapshot_event(record, notebook_id=record.id))
            entry = self._entries[record.id]
            if entry.notebook is None:
                continue
            seen: set[tuple[type[Body], str]] = set()
            for event in [
                *entry.notebook._snapshot(),
                *entry.log.snapshot(),
            ]:
                identity = _identity(event)
                if identity not in seen and event.visible_in(notebook_id):
                    seen.add(identity)
                    events.append(event)
        return events

    def events(
        self,
        cursor: str | None = None,
        *,
        notebook_id: str | None = None,
        types: Collection[str] | None = None,
        run_id: str | None = None,
    ) -> list[RoutedEvent]:
        """Return a snapshot or replay followed by `ready`.

        A cursor requests the events after it. A cursor this stream did not
        issue, or whose events it no longer has, returns `reset` and a
        snapshot.
        """
        scope = None
        if notebook_id is not None:
            if notebook_id not in self._records:
                raise NotFound(f"no notebook {notebook_id}")
            scope = self._records[notebook_id].id
        ready = RoutedEvent(
            protocol.ReadyEvent(data={}, id=self._stream.cursor)
        )
        if cursor is None:
            events = self._snapshot(scope)
        else:
            position = self._stream.position(cursor)
            missed = None if position is None else self._stream.since(position)
            if missed is None:
                events = [
                    RoutedEvent(protocol.ResetEvent(data={})),
                    *self._snapshot(scope),
                ]
            else:
                events = [e for e in missed if e.visible_in(notebook_id)]
        return [e for e in [*events, ready] if e.wanted(types, run_id)]

    def expire(self) -> None:
        """Remove scratch results whose retention has ended."""
        with self._stream.deferred():
            for entry in list(self._entries.values()):
                for event in entry.log.expire(self.retention):
                    self._stream.append(event)

    def subscribe(
        self,
        listener: Listener,
        *,
        notebook_id: str | None = None,
        types: Collection[str] | None = None,
        run_id: str | None = None,
    ) -> Callable[[], None]:
        """Subscribe to matching events and return an unsubscribe function."""

        def filtered(event: RoutedEvent) -> None:
            if event.visible_in(notebook_id) and event.wanted(types, run_id):
                listener(event)

        return self._stream.subscribe(filtered)
