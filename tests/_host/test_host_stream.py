# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from marimo._host import protocol
from marimo._host.model import (
    Attachment,
    ConsoleLine,
    Executing,
    Execution,
    HostState,
    Indexed,
    Notebook,
    Partial,
    Project,
    Running,
    Runtime,
)
from marimo._host.stream import diff, snapshot
from marimo._types.ids import (
    AttachmentId,
    ExecutionId,
    NotebookId,
    ProjectId,
    RuntimeId,
)

NOW = datetime(2026, 10, 1, 9, 14, 2, tzinfo=timezone.utc)
PROJECT = ProjectId("p1")
NOTEBOOK = NotebookId("n1")
RUNTIME = RuntimeId("r1")
HOST = protocol.Host(operations=["runtime.start"])


def populated() -> HostState:
    runtime = Runtime(RUNTIME, NOW, sandbox=True, lifecycle=Running())
    attachment = Attachment(AttachmentId("a1"), "browser", "Chrome", NOW)
    execution = Execution(
        ExecutionId("e1"),
        "print(1)",
        lifecycle=Executing(NOW),
        console=(ConsoleLine("stdout", "1\n"),),
    )
    project = Project(PROJECT, "forecasting", Path("/p"), Indexed())
    notebook = Notebook(
        NOTEBOOK,
        PROJECT,
        "forecasts",
        Path("forecasts.py"),
        NOW,
        runtime=runtime,
        attachments={attachment.id: attachment},
        executions={execution.id: execution},
    )
    return HostState().with_project(project).with_notebook(notebook)


def test_snapshot_lists_parents_before_children() -> None:
    events = snapshot(HOST, populated(), at=NOW)
    assert [e.name for e in events] == [
        "host",
        "project",
        "notebook",
        "runtime",
        "attachment",
        "execution",
        "console",
    ]
    # Everything a notebook owns is tagged with it; the catalog's own
    # objects are not.
    assert [e.notebook_id for e in events[:2]] == [None, None]
    assert all(e.notebook_id == NOTEBOOK for e in events[2:])


def test_removing_a_notebook_removes_children_first() -> None:
    state = populated()
    emptied = replace(state, notebooks={})

    assert [e.name for e in diff(state, emptied, at=NOW)] == [
        "execution",  # the run in flight, now interrupted
        "execution.removed",
        "attachment.removed",
        "runtime.removed",
        "notebook.removed",
    ]


def test_only_what_changed_is_sent() -> None:
    state = populated()
    notebook = state.notebooks[NOTEBOOK]

    # A runtime leaving does not re-send its notebook or attachments.
    stopped = state.with_runtime(notebook, None)
    assert [e.name for e in diff(state, stopped, at=NOW)] == [
        "runtime.removed"
    ]

    # One more line printed is one console message, and nothing else.
    execution = notebook.executions[ExecutionId("e1")]
    printed = replace(
        execution, console=(*execution.console, ConsoleLine("stderr", "!"))
    )
    louder = state.with_notebook(
        replace(notebook, executions={execution.id: printed})
    )
    [event] = diff(state, louder, at=NOW)
    assert event.name == "console"
    assert isinstance(event.data, protocol.ConsoleMessage)
    assert event.data.console.text == "!"

    project = replace(state.projects[PROJECT], index=Partial("stopped"))
    assert [
        e.name for e in diff(state, state.with_project(project), at=NOW)
    ] == ["project"]

    assert diff(state, state, at=NOW) == []
