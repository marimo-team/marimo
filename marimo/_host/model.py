# Copyright 2026 Marimo. All rights reserved.
"""What a host knows about its projects, notebooks, runtimes, and executions.

A `HostState` is a snapshot of one host at one moment. It holds projects
and notebooks by id. A notebook holds at most one runtime, and owns its
attachments and executions outright, so a kernel restart disturbs
neither and nothing outlives its notebook. Where the protocol states a
rule in prose, this module makes it a fact of the structure instead.

Every type here is an immutable value. Changing a state means building a
new one, and two states are equal when they describe the same host.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal

from marimo._types.ids import (
    AttachmentId,
    ExecutionId,
    NotebookId,
    ProjectId,
    RuntimeId,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime
    from pathlib import Path

# Projects


@dataclass(frozen=True)
class Indexing:
    """The project's notebooks are still being found."""


@dataclass(frozen=True)
class Indexed:
    """Every notebook in the project has been found."""


@dataclass(frozen=True)
class Partial:
    """The search for notebooks stopped short.

    Some notebooks under the root are not listed and cannot be reached by
    id. `reason` says why the search stopped, in words meant for people.
    """

    reason: str


IndexStatus = Indexing | Indexed | Partial
"""How complete a project's list of notebooks is."""


@dataclass(frozen=True)
class Project:
    """A group of notebooks presented together, usually a directory."""

    id: ProjectId
    name: str
    """A label for people, usually the directory's name."""
    root: Path | None
    """The directory's absolute path, or `None` for a project with none."""
    index: IndexStatus


# Runtimes


@dataclass(frozen=True)
class Starting:
    """The kernel is coming up and does not accept work yet."""

    progress: str | None = None
    """The current step, in words for people, such as preparing the
    environment."""


@dataclass(frozen=True)
class Running:
    """The kernel is up and accepting work."""


@dataclass(frozen=True)
class Failed:
    """The kernel could not start, or exited without being asked to.

    A failed runtime is still a runtime, so whoever is attached can learn
    `reason`. Stopping it and starting again brings a fresh one.
    """

    reason: str


@dataclass(frozen=True)
class Terminating:
    """The kernel has been told to shut down and has not yet exited."""


Lifecycle = Starting | Running | Failed | Terminating
"""Where a runtime is in its life.

There is no ended variant. A runtime whose kernel has exited on request
is removed from its notebook rather than kept in a final state.
"""


@dataclass(frozen=True)
class Runtime:
    """A kernel serving one notebook.

    A runtime keeps its id for as long as it exists, through any number
    of kernel restarts. Each kernel it has run is one generation, counted
    from zero. A report from a kernel names its generation, which is how
    a kernel from before a restart is told apart from the current one and
    kept from failing or reviving its replacement by reporting late.
    """

    id: RuntimeId
    started_at: datetime
    """When the runtime was created. Restarts do not change it."""
    sandbox: bool
    """Whether the kernel runs in an environment built from the
    dependencies the notebook declares inline."""
    generation: int = 0
    """How many restarts there have been."""
    marimo_version: str | None = None
    """The version of marimo in the kernel, once the kernel has reported
    it. `None` while a kernel is starting."""
    lifecycle: Lifecycle = field(default_factory=Starting)


# Attachments and executions


@dataclass(frozen=True)
class Attachment:
    """Something connected to a notebook: a browser tab, an editor, an agent.

    An attachment lasts exactly as long as its connection. It belongs to
    the notebook rather than the runtime, so it is unaffected by a
    kernel restart.
    """

    id: AttachmentId
    kind: str
    """Such as `browser`, `editor`, or `agent`."""
    name: str | None
    """A label for people, such as the browser's name."""
    since: datetime


FinalStatus = Literal["succeeded", "failed", "interrupted"]
"""How an execution ended: cleanly, with errors, or cut short."""

ExecutionStatus = Literal["queued", "running"] | FinalStatus
"""Where an execution is: waiting for the kernel, running, or ended."""


@dataclass(frozen=True)
class Display:
    """Output as marimo would show it."""

    mimetype: str
    data: str


@dataclass(frozen=True)
class ExecutionError:
    """One reason an execution failed."""

    kind: Literal["exception", "syntax", "interruption", "internal"]
    name: str | None
    """The exception class, when `kind` is `exception`."""
    message: str
    traceback: str | None


@dataclass(frozen=True)
class ConsoleLine:
    """One piece of text written to stdout or stderr."""

    name: Literal["stdout", "stderr"]
    text: str


@dataclass(frozen=True)
class Queued:
    """The kernel has not picked the code up yet."""


@dataclass(frozen=True)
class Executing:
    """The kernel is running the code."""

    started_at: datetime


@dataclass(frozen=True)
class Finished:
    """The execution is over, one way or another."""

    status: FinalStatus
    completed_at: datetime
    started_at: datetime | None
    """`None` for an execution that ended before the kernel began it."""
    errors: tuple[ExecutionError, ...] = ()


@dataclass(frozen=True)
class Execution:
    """One run of a piece of code against a notebook's runtime.

    The code runs in the kernel's scratchpad and never becomes a cell.
    What is known about an execution grows with its lifecycle: a start
    time once the kernel begins, then a final status, an end time, and
    any errors. The properties read those out as flat values.

    `output` is one value that is replaced, not appended to, as the code
    produces more. `console` keeps everything printed so far, so that a
    reader arriving mid-run can catch up.

    A finished execution is kept until it is forgotten, so a repeated
    request can be answered with the same result.
    """

    id: ExecutionId
    code: str
    lifecycle: Queued | Executing | Finished = Queued()
    output: Display | None = None
    console: tuple[ConsoleLine, ...] = ()

    @property
    def final(self) -> bool:
        return isinstance(self.lifecycle, Finished)

    @property
    def status(self) -> ExecutionStatus:
        match self.lifecycle:
            case Queued():
                return "queued"
            case Executing():
                return "running"
            case Finished():
                return self.lifecycle.status

    @property
    def started_at(self) -> datetime | None:
        match self.lifecycle:
            case Queued():
                return None
            case Executing() | Finished():
                return self.lifecycle.started_at

    @property
    def completed_at(self) -> datetime | None:
        if isinstance(self.lifecycle, Finished):
            return self.lifecycle.completed_at
        return None

    @property
    def errors(self) -> tuple[ExecutionError, ...]:
        if isinstance(self.lifecycle, Finished):
            return self.lifecycle.errors
        return ()


# Notebooks


@dataclass(frozen=True)
class Notebook:
    """A marimo notebook, with whatever is running on it or attached to it.

    A notebook exists while anything refers to it: its file, a runtime,
    an attachment, or an execution. So it may have a file and no runtime,
    or a runtime and no file, as when the file is deleted while a kernel
    is still serving it.
    """

    id: NotebookId
    project_id: ProjectId
    title: str
    """A title for people."""
    path: Path | None
    """Where the file is, relative to the project root. `None` once the
    file is gone."""
    updated_at: datetime | None
    """When the file was last modified, as last observed."""
    runtime: Runtime | None = None
    attachments: Mapping[AttachmentId, Attachment] = field(
        default_factory=dict
    )
    """By id, in the order they attached."""
    executions: Mapping[ExecutionId, Execution] = field(default_factory=dict)
    """By id, in the order they were requested."""

    @property
    def referenced(self) -> bool:
        """Whether anything besides the file refers to this notebook."""
        return (
            self.runtime is not None
            or bool(self.attachments)
            or bool(self.executions)
        )

    def running_execution(self) -> Execution | None:
        """The execution not yet finished, if any. There is at most one."""
        for execution in self.executions.values():
            if not execution.final:
                return execution
        return None


# The host


@dataclass(frozen=True)
class HostState:
    """Everything a host knows, as of one moment.

    Each `with_*` method returns a new state sharing everything the change
    did not touch. Runtimes are found by walking the notebooks; a host has
    tens of notebooks, not thousands.
    """

    projects: Mapping[ProjectId, Project] = field(default_factory=dict)
    notebooks: Mapping[NotebookId, Notebook] = field(default_factory=dict)

    def locate(self, runtime_id: RuntimeId) -> tuple[Notebook, Runtime] | None:
        """Returns the runtime with this id and the notebook it serves.

        `None` if no notebook currently holds it, as for a runtime that
        has ended.
        """
        for notebook in self.notebooks.values():
            runtime = notebook.runtime
            if runtime is not None and runtime.id == runtime_id:
                return notebook, runtime
        return None

    def with_project(self, project: Project) -> HostState:
        """Returns a state with `project` added, or replaced by id."""
        return replace(self, projects={**self.projects, project.id: project})

    def with_notebook(self, notebook: Notebook) -> HostState:
        """Returns a state with `notebook` added, or replaced by id.

        A notebook with no file and nothing referring to it is removed
        instead, since nothing is left to know about. Every change to a
        notebook passes through here, so that rule holds everywhere.

        Raises:
            KeyError: If `notebook.project_id` is not a project in this state.
        """
        if notebook.project_id not in self.projects:
            raise KeyError(f"Unknown project: {notebook.project_id}")
        if notebook.path is None and not notebook.referenced:
            return self.without_notebook(notebook.id)
        return replace(
            self, notebooks={**self.notebooks, notebook.id: notebook}
        )

    def without_notebook(self, notebook_id: NotebookId) -> HostState:
        """Returns a state without this notebook, if it was present."""
        notebooks = {
            other: notebook
            for other, notebook in self.notebooks.items()
            if other != notebook_id
        }
        return replace(self, notebooks=notebooks)

    def with_runtime(
        self, notebook: Notebook, runtime: Runtime | None
    ) -> HostState:
        """Returns a state in which `notebook` holds `runtime`.

        `None` leaves the notebook with no runtime.
        """
        return self.with_notebook(replace(notebook, runtime=runtime))
