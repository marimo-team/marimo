# Copyright 2026 Marimo. All rights reserved.
"""Events that tell a client what a host has and what changed.

Parents come before children, removals go children first, and every
event about a notebook is tagged with it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from marimo._host import protocol, wire
from marimo._host.model import HostState
from marimo._types.ids import RuntimeId

if TYPE_CHECKING:
    from datetime import datetime

    from marimo._host.model import (
        Attachment,
        ConsoleLine,
        Execution,
        Notebook,
        Project,
        Runtime,
    )
    from marimo._types.ids import NotebookId

Message = (
    protocol.HostMessage
    | protocol.ProjectMessage
    | protocol.NotebookMessage
    | protocol.RuntimeMessage
    | protocol.AttachmentMessage
    | protocol.ExecutionMessage
    | protocol.ConsoleMessage
    | protocol.RemovedMessage
)
"""The data of an event about an object or console text."""

CATALOG = ("host", "project", "notebook", "runtime", "attachment")
"""The kinds the catalog stream carries."""

NOTEBOOK = ("notebook", "runtime", "attachment", "execution", "console")
"""The kinds a notebook's stream carries."""


@dataclass(frozen=True)
class Event:
    """One event on a stream.

    `id` is the cursor; a snapshot's events have none. `data` is `None`
    for `ready` and `reset`.
    """

    name: str
    data: Message | None = None
    id: int | None = None
    notebook_id: NotebookId | None = None

    @property
    def kind(self) -> str:
        """The kind of object, without any `.removed`."""
        return self.name.split(".")[0]

    def runtime_id(self) -> RuntimeId | None:
        """The runtime this event is about, for runtime events."""
        # The protocol's ids are plain strings; the host's are NewTypes.
        if isinstance(self.data, protocol.RuntimeMessage):
            return RuntimeId(self.data.runtime.id)
        if self.name == "runtime.removed" and isinstance(
            self.data, protocol.RemovedMessage
        ):
            return RuntimeId(self.data.id)
        return None


def snapshot(
    host: protocol.Host, state: HostState, *, at: datetime
) -> list[Event]:
    """Returns everything a host has, as events, parents before children."""
    first = Event("host", protocol.HostMessage(host=host))
    return [first, *diff(HostState(), state, at=at)]


def diff(before: HostState, after: HostState, *, at: datetime) -> list[Event]:
    """Returns the events that take a client from `before` to `after`.

    An execution still in flight when it disappears is sent once more,
    interrupted at `at`, before its removal.
    """
    events: list[Event] = []

    for project in after.projects.values():
        previous_project = before.projects.get(project.id)
        if previous_project is None or wire.project(
            previous_project
        ) != wire.project(project):
            events.append(_project(project))

    for notebook in after.notebooks.values():
        previous = before.notebooks.get(notebook.id)
        if previous is None or wire.notebook(previous) != wire.notebook(
            notebook
        ):
            events.append(_notebook(notebook))
        events.extend(_diff_children(previous, notebook, at))

    for notebook in before.notebooks.values():
        if notebook.id not in after.notebooks:
            events.extend(_remove_children(notebook, at))
            events.append(_removed("notebook", notebook.id, notebook.id))

    for project in before.projects.values():
        if project.id not in after.projects:
            events.append(_removed("project", project.id, None))

    return events


def _diff_children(
    before: Notebook | None, after: Notebook, at: datetime
) -> list[Event]:
    events: list[Event] = []
    nid = after.id

    # The runtime: a change, an arrival, or a departure.
    previous = None if before is None else before.runtime
    current = after.runtime
    if current is not None and (
        previous is None
        or previous.id != current.id
        or wire.runtime(nid, previous) != wire.runtime(nid, current)
    ):
        if previous is not None and previous.id != current.id:
            events.append(_removed("runtime", previous.id, nid))
        events.append(_runtime(nid, current))
    elif current is None and previous is not None:
        events.append(_removed("runtime", previous.id, nid))

    # Attachments only arrive and depart; they do not change.
    known = {} if before is None else before.attachments
    for attachment in after.attachments.values():
        if attachment.id not in known:
            events.append(_attachment(nid, attachment))
    for attachment_id in known:
        if attachment_id not in after.attachments:
            events.append(_removed("attachment", attachment_id, nid))

    # Executions change as they run, print, and finish.
    known_executions = {} if before is None else before.executions
    for execution in after.executions.values():
        previous_execution = known_executions.get(execution.id)
        if previous_execution is None or wire.execution(
            nid, previous_execution
        ) != wire.execution(nid, execution):
            events.append(_execution(nid, wire.execution(nid, execution)))
        printed = (
            0
            if previous_execution is None
            else len(previous_execution.console)
        )
        for line in execution.console[printed:]:
            events.append(_console(nid, execution, line))
    for execution in known_executions.values():
        if execution.id not in after.executions:
            events.extend(_remove_execution(nid, execution, at))

    return events


def _remove_children(notebook: Notebook, at: datetime) -> list[Event]:
    events: list[Event] = []
    for execution in notebook.executions.values():
        events.extend(_remove_execution(notebook.id, execution, at))
    for attachment_id in notebook.attachments:
        events.append(_removed("attachment", attachment_id, notebook.id))
    if notebook.runtime is not None:
        events.append(_removed("runtime", notebook.runtime.id, notebook.id))
    return events


def _remove_execution(
    nid: NotebookId, execution: Execution, at: datetime
) -> list[Event]:
    events: list[Event] = []
    if not execution.final:
        # Say how it ended before it goes.
        events.append(_execution(nid, wire.interrupted(nid, execution, at)))
    events.append(_removed("execution", execution.id, nid))
    return events


def _project(project: Project) -> Event:
    return Event(
        "project", protocol.ProjectMessage(project=wire.project(project))
    )


def _notebook(notebook: Notebook) -> Event:
    return Event(
        "notebook",
        protocol.NotebookMessage(notebook=wire.notebook(notebook)),
        notebook_id=notebook.id,
    )


def _runtime(nid: NotebookId, runtime: Runtime) -> Event:
    return Event(
        "runtime",
        protocol.RuntimeMessage(runtime=wire.runtime(nid, runtime)),
        notebook_id=nid,
    )


def _attachment(nid: NotebookId, attachment: Attachment) -> Event:
    return Event(
        "attachment",
        protocol.AttachmentMessage(
            attachment=wire.attachment(nid, attachment)
        ),
        notebook_id=nid,
    )


def _execution(nid: NotebookId, execution: protocol.Execution) -> Event:
    return Event(
        "execution",
        protocol.ExecutionMessage(execution=execution),
        notebook_id=nid,
    )


def _console(
    nid: NotebookId, execution: Execution, line: ConsoleLine
) -> Event:
    return Event(
        "console",
        protocol.ConsoleMessage(console=wire.console(execution, line)),
        notebook_id=nid,
    )


def _removed(kind: str, object_id: str, nid: NotebookId | None) -> Event:
    return Event(
        f"{kind}.removed",
        protocol.RemovedMessage(id=object_id),
        notebook_id=nid,
    )
