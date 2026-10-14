# Copyright 2026 Marimo. All rights reserved.
"""Projects, notebooks, and event subscriptions for a marimo host."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from time import monotonic
from typing import TYPE_CHECKING

from marimo._core import protocol
from marimo._core.backend import Backend
from marimo._core.errors import NotFound
from marimo._core.notebook import Notebook
from marimo._core.run_log import RetentionPolicy, RunLog
from marimo._core.stream import Event, Listener, Stream, message

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterator, Sequence


@dataclass
class _Entry:
    """A notebook, the run history kept for it, and its subscription."""

    notebook: Notebook
    log: RunLog
    unsubscribe: Callable[[], None]


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


def _identity(event: Event) -> tuple[str, str]:
    assert event.kind is not None
    return event.name, getattr(event.data, event.kind).id


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
        self._entries: dict[str, _Entry] = {}

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
        backend: Backend,
        *,
        request_id: str | None = None,
    ) -> Notebook:
        """Register a notebook and its backend."""
        if record.id in self._records:
            raise ValueError(f"notebook {record.id} is already in the catalog")
        if record.project_id not in self._projects:
            raise ValueError(
                f"project {record.project_id} is not in the catalog"
            )
        notebook = Notebook(record.id, backend)
        log = RunLog(lambda: self.clock())

        def publish(event: Event) -> None:
            removals = log.observe(event)
            self._stream.append(event)
            for removal in removals:
                self._stream.append(removal)

        self._records[record.id] = deepcopy(record)
        self._entries[record.id] = _Entry(
            notebook, log, notebook.subscribe(publish)
        )
        self._stream.publish(
            record, notebook_id=record.id, request_id=request_id
        )
        return notebook

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
        entry = self._entries.pop(notebook_id, None)
        if entry is None:
            return
        record = self._records.pop(notebook_id)
        entry.notebook._dispose(request_id=request_id)
        with self._stream.deferred():
            for event in entry.log.clear():
                self._stream.append(event)
        entry.unsubscribe()
        self._stream.remove(
            "notebook",
            record.id,
            notebook_id=record.id,
            request_id=request_id,
        )

    def notebook(self, notebook_id: str) -> Notebook:
        """Return a notebook or raise `NotFound`."""
        entry = self._entries.get(notebook_id)
        if entry is None:
            raise NotFound(f"no notebook {notebook_id}")
        return entry.notebook

    def _snapshot(
        self, notebook_id: protocol.NotebookId | None = None
    ) -> list[Event]:
        """Return catalog or notebook state with retained run history."""
        if notebook_id is not None:
            records = [self._records[notebook_id]]
            events: list[Event] = []
        else:
            records = list(self._records.values())
            events = [Event("host", message(self._host))]
            events.extend(
                Event("project", message(p)) for p in self._projects.values()
            )
        for record in records:
            events.append(
                Event("notebook", message(record), notebook_id=record.id)
            )
            entry = self._entries[record.id]
            seen: set[tuple[str, str]] = set()
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
        cursor: int | None = None,
        *,
        notebook_id: str | None = None,
        types: Collection[str] | None = None,
        run_id: str | None = None,
    ) -> list[Event]:
        """Return a snapshot or replay followed by `ready`.

        A cursor requests the events after it. An unavailable cursor returns
        `reset` and a snapshot.
        """
        scope = None if notebook_id is None else self.notebook(notebook_id).id
        ready = Event("ready", id=self._stream.last_id)
        if cursor is None:
            events = self._snapshot(scope)
        else:
            missed = self._stream.since(cursor)
            if missed is None:
                events = [Event("reset"), *self._snapshot(scope)]
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

        def filtered(event: Event) -> None:
            if event.visible_in(notebook_id) and event.wanted(types, run_id):
                listener(event)

        return self._stream.subscribe(filtered)
