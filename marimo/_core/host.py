# Copyright 2026 Marimo. All rights reserved.
"""Projects, notebooks, and event subscriptions for a marimo host."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from time import monotonic
from typing import TYPE_CHECKING

from marimo._core import protocol
from marimo._core.backend import Backend
from marimo._core.errors import NotFound
from marimo._core.execution_state import RetentionPolicy
from marimo._core.notebook import Notebook
from marimo._core.stream import Event, Listener, Stream, message

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterator, Sequence


class _NotebookRecords(Mapping[str, protocol.Notebook]):
    """A catalog view whose readers own their copies of mutable records."""

    def __init__(self, records: Mapping[str, protocol.Notebook]) -> None:
        self._records = records

    def __getitem__(self, key: str) -> protocol.Notebook:
        return deepcopy(self._records[key])

    def __iter__(self) -> Iterator[str]:
        return iter(self._records)

    def __len__(self) -> int:
        return len(self._records)


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
        self._notebooks: dict[str, Notebook] = {}

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
        """Register a notebook and the backend that runs it."""
        if record.id in self._records:
            raise ValueError(f"notebook {record.id} is already in the catalog")
        if record.project_id not in self._projects:
            raise ValueError(
                f"project {record.project_id} is not in the catalog"
            )
        notebook = Notebook(
            record.id, backend, self._stream, self.retention, self.clock
        )
        self._records[record.id] = deepcopy(record)
        self._notebooks[record.id] = notebook
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
        notebook = self._notebooks.pop(notebook_id, None)
        if notebook is None:
            return
        del self._records[notebook.id]
        notebook._dispose(request_id=request_id)
        self._stream.remove(
            "notebook",
            notebook.id,
            notebook_id=notebook.id,
            request_id=request_id,
        )

    def notebook(self, notebook_id: str) -> Notebook:
        """Return a notebook or raise `NotFound`."""
        notebook = self._notebooks.get(notebook_id)
        if notebook is None:
            raise NotFound(f"no notebook {notebook_id}")
        return notebook

    def _snapshot(
        self, notebook_id: protocol.NotebookId | None = None
    ) -> list[Event]:
        """Return snapshot events for the catalog or a single notebook.

        Catalog snapshots contain the host, projects, then notebooks with
        their runtimes and attachments. Notebook snapshots also include
        runs, executions, and outputs.
        """
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
            events.extend(
                e
                for e in self._notebooks[record.id]._snapshot()
                if e.visible_in(notebook_id)
            )
        return events

    def events(
        self,
        cursor: int | None = None,
        *,
        notebook_id: str | None = None,
        types: Collection[str] | None = None,
        run_id: str | None = None,
    ) -> list[Event]:
        """Return initial events followed by `ready` with the latest cursor.

        Replay events after `cursor`, or return a snapshot if no cursor
        is given. An unavailable cursor produces `reset` and a snapshot.
        A run filter includes only that run, its executions, and their items.
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
        """Sweep results according to the host's retention policy."""
        for notebook in list(self._notebooks.values()):
            notebook.expire()

    def subscribe(
        self,
        listener: Listener,
        *,
        notebook_id: str | None = None,
        types: Collection[str] | None = None,
        run_id: str | None = None,
    ) -> Callable[[], None]:
        """Subscribe to matching live events; return an unsubscribe function."""

        def filtered(event: Event) -> None:
            if event.visible_in(notebook_id) and event.wanted(types, run_id):
                listener(event)

        return self._stream.subscribe(filtered)
