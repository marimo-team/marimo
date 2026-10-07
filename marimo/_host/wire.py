# Copyright 2026 Marimo. All rights reserved.
"""Turns host state into the protocol's objects.

Each function translates one kind of object and nothing more.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from marimo._host import model, protocol
from marimo._utils.assert_never import assert_never

if TYPE_CHECKING:
    from datetime import datetime

    from marimo._types.ids import NotebookId


def project(p: model.Project) -> protocol.Project:
    """Returns the protocol object for a project."""
    status: protocol.ProjectStatus
    message: str | None
    match p.index:
        case model.Indexing():
            status, message = "indexing", None
        case model.Indexed():
            status, message = "indexed", None
        case model.Partial(reason):
            status, message = "partial", reason
        case _:
            assert_never(p.index)
    return protocol.Project(
        id=p.id,
        name=p.name,
        root=None if p.root is None else str(p.root),
        status=status,
        message=message,
    )


def notebook(n: model.Notebook) -> protocol.Notebook:
    """Returns the protocol object for a notebook."""
    return protocol.Notebook(
        id=n.id,
        project_id=n.project_id,
        path=None if n.path is None else str(n.path),
        title=n.title,
        updated_at=n.updated_at,
    )


def runtime(notebook_id: NotebookId, r: model.Runtime) -> protocol.Runtime:
    """Returns the protocol object for a runtime.

    `message` is the progress while starting and the reason when failed.
    """
    status: protocol.RuntimeStatus
    message: str | None
    match r.lifecycle:
        case model.Starting(progress):
            status, message = "starting", progress
        case model.Running():
            status, message = "running", None
        case model.Failed(reason):
            status, message = "failed", reason
        case model.Terminating():
            status, message = "terminating", None
        case _:
            assert_never(r.lifecycle)
    return protocol.Runtime(
        id=r.id,
        notebook_id=notebook_id,
        status=status,
        message=message,
        sandbox=r.sandbox,
        generation=r.generation,
        marimo_version=r.marimo_version,
        started_at=r.started_at,
    )


def attachment(
    notebook_id: NotebookId, a: model.Attachment
) -> protocol.Attachment:
    """Returns the protocol object for an attachment."""
    return protocol.Attachment(
        id=a.id,
        notebook_id=notebook_id,
        kind=a.kind,
        name=a.name,
        since=a.since,
    )


def execution(
    notebook_id: NotebookId, e: model.Execution
) -> protocol.Execution:
    """Returns the protocol object for an execution.

    Console text is not part of it; it travels as separate messages.
    """
    return protocol.Execution(
        id=e.id,
        notebook_id=notebook_id,
        code=e.code,
        status=e.status,
        output=(
            None
            if e.output is None
            else protocol.Output(
                mimetype=e.output.mimetype, data=e.output.data
            )
        ),
        errors=[
            protocol.ExecutionError(
                kind=error.kind,
                name=error.name,
                message=error.message,
                traceback=error.traceback,
            )
            for error in e.errors
        ],
        started_at=e.started_at,
        completed_at=e.completed_at,
    )


def interrupted(
    notebook_id: NotebookId, e: model.Execution, at: datetime
) -> protocol.Execution:
    """Returns an execution as it would look had it been interrupted at `at`.

    An execution that never began keeps a null start time.
    """
    ended = model.Finished("interrupted", at, e.started_at)
    return execution(notebook_id, replace(e, lifecycle=ended))


def console(e: model.Execution, line: model.ConsoleLine) -> protocol.Console:
    """Returns the protocol object for one line an execution printed."""
    return protocol.Console(execution_id=e.id, name=line.name, text=line.text)
