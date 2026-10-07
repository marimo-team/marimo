# Copyright 2026 Marimo. All rights reserved.
"""The rules for changing host state.

`apply` takes a state and one change and returns the next state along
with any kernel work it calls for. Commands come from clients and may
be refused; observations report what already happened and never are.

The runtime lifecycle, by change:

    lifecycle     start      restart    stop         ready    exited
    no runtime    Starting   no-runtime no-runtime   -        -
    Starting      same       conflict   Terminating  Running  Failed
    Running       same       Starting+  Terminating  -        Failed
    Failed        same       conflict   removed      -        -
    Terminating   same       conflict   same         -        removed

`same` returns the state unchanged, `Starting+` begins the next
generation, `removed` takes the runtime away, `-` ignores the change,
and the rest raise. Stopping or restarting forgets the notebook's
executions.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from marimo._host.model import (
    Attachment,
    ConsoleLine,
    Display,
    Executing,
    Execution,
    ExecutionError,
    Failed,
    Finished,
    HostState,
    Notebook,
    Project,
    Queued,
    Running,
    Runtime,
    Starting,
    Terminating,
)
from marimo._utils.assert_never import assert_never

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from marimo._host.model import FinalStatus
    from marimo._types.ids import (
        AttachmentId,
        ExecutionId,
        NotebookId,
        RuntimeId,
    )

# Commands


@dataclass(frozen=True)
class StartRuntime:
    """Ensures a notebook has a runtime.

    A notebook that already has one, in any state, is left alone.
    """

    notebook_id: NotebookId
    runtime_id: RuntimeId
    """The id for the runtime, used only if one has to be created."""
    started_at: datetime
    sandbox: bool


@dataclass(frozen=True)
class RestartRuntime:
    """Replaces a running kernel, keeping the runtime.

    Raises `Conflict` unless the runtime is running.
    """

    notebook_id: NotebookId


@dataclass(frozen=True)
class StopRuntime:
    """Ends a notebook's runtime.

    A live kernel is told to exit and the runtime leaves once it has. A
    failed runtime leaves at once.
    """

    notebook_id: NotebookId


@dataclass(frozen=True)
class Attach:
    """Connects something to a notebook.

    Raises `Conflict` for an attachment id the notebook already has.
    """

    notebook_id: NotebookId
    attachment: Attachment


@dataclass(frozen=True)
class ExecuteCode:
    """Queues code to run on the notebook's runtime.

    Raises `Conflict` unless the runtime is running and nothing else is
    in progress.
    """

    notebook_id: NotebookId
    execution_id: ExecutionId
    code: str


Command = StartRuntime | RestartRuntime | StopRuntime | Attach | ExecuteCode
"""A change that carries a client's intent and may be refused."""

# Observations


@dataclass(frozen=True)
class StartupProgress:
    """Reports how far a starting kernel has gotten.

    Ignored unless the runtime is starting.
    """

    runtime_id: RuntimeId
    generation: int
    message: str


@dataclass(frozen=True)
class KernelReady:
    """Reports that the kernel is up.

    Ignored unless the runtime is starting, so a kernel that comes up
    while being stopped stays terminating.
    """

    runtime_id: RuntimeId
    generation: int
    marimo_version: str | None


@dataclass(frozen=True)
class KernelExited:
    """Reports that the kernel is gone, asked or not.

    A terminating runtime leaves; a starting or running one fails with
    `reason`. Ignored once the runtime has failed.
    """

    runtime_id: RuntimeId
    generation: int
    reason: str


@dataclass(frozen=True)
class Detach:
    """Reports that an attachment's connection closed."""

    notebook_id: NotebookId
    attachment_id: AttachmentId


@dataclass(frozen=True)
class ExecutionStarted:
    """Reports that the kernel began running an execution."""

    notebook_id: NotebookId
    execution_id: ExecutionId
    at: datetime


@dataclass(frozen=True)
class ExecutionShown:
    """Reports an execution's output so far, replacing what was shown."""

    notebook_id: NotebookId
    execution_id: ExecutionId
    output: Display


@dataclass(frozen=True)
class ExecutionPrinted:
    """Reports text an execution printed."""

    notebook_id: NotebookId
    execution_id: ExecutionId
    line: ConsoleLine


@dataclass(frozen=True)
class ExecutionEnded:
    """Reports that an execution reached a final status."""

    notebook_id: NotebookId
    execution_id: ExecutionId
    status: FinalStatus
    errors: tuple[ExecutionError, ...]
    at: datetime


@dataclass(frozen=True)
class ExecutionForgotten:
    """Reports that a finished execution is no longer kept.

    Ignored for one still in progress.
    """

    notebook_id: NotebookId
    execution_id: ExecutionId


@dataclass(frozen=True)
class IndexProject:
    """Reports a project as it now is, leaving its notebooks as they are."""

    project: Project


@dataclass(frozen=True)
class NotebookSeen:
    """Reports a notebook's file as it now is.

    Only the file's facts change; the runtime, attachments, and
    executions already held stay.
    """

    notebook: Notebook


@dataclass(frozen=True)
class NotebookGone:
    """Reports that a notebook's file is no longer there.

    The notebook stays, without a path, while anything refers to it.
    """

    notebook_id: NotebookId


Observation = (
    StartupProgress
    | KernelReady
    | KernelExited
    | Detach
    | ExecutionStarted
    | ExecutionShown
    | ExecutionPrinted
    | ExecutionEnded
    | ExecutionForgotten
    | IndexProject
    | NotebookSeen
    | NotebookGone
)
"""A change that reports what already happened and is never refused.

An observation about something the host no longer has, or about a kernel
generation that is not the runtime's current one, is ignored."""

# Actions


@dataclass(frozen=True)
class StartKernel:
    """Asks for a kernel for one generation of a runtime.

    The runtime answers with `StartupProgress`, `KernelReady`, and
    eventually `KernelExited`, each naming this generation.
    """

    notebook_id: NotebookId
    runtime_id: RuntimeId
    generation: int
    sandbox: bool


@dataclass(frozen=True)
class StopKernel:
    """Asks for the kernel running one generation to be shut down."""

    runtime_id: RuntimeId
    generation: int


Action = StartKernel | StopKernel
"""Kernel work that `apply` cannot do itself."""


@dataclass(frozen=True)
class Outcome:
    """The next state, and the kernel work to do once it is in place."""

    state: HostState
    actions: tuple[Action, ...] = ()
    """To be performed in this order, after `state` is installed."""


class Conflict(Exception):
    """A command does not fit the notebook's current state."""


class NoRuntime(Conflict):
    """A command needs a runtime and the notebook has none."""


class NotFound(KeyError):
    """A command names a notebook or runtime the host does not have."""


def apply(state: HostState, change: Command | Observation) -> Outcome:
    """Applies one change to `state`.

    A change with no effect returns `state` itself.

    Raises:
        NotFound: If a command names something the host does not have.
        NoRuntime: If a command needs a runtime the notebook lacks.
        Conflict: If a command does not fit the notebook's state.
    """
    match change:
        case IndexProject():
            return Outcome(state.with_project(change.project))
        case NotebookSeen():
            return _notebook_seen(state, change.notebook)
        case NotebookGone():
            return _notebook_gone(state, change.notebook_id)
        case StartupProgress() | KernelReady() | KernelExited():
            return _from_kernel(state, change)
        case _:
            pass

    notebook = state.notebooks.get(change.notebook_id)
    if notebook is None:
        if isinstance(change, Command):
            raise NotFound(change.notebook_id)
        return Outcome(state)

    match change:
        case StartRuntime():
            return _start(state, notebook, change)
        case RestartRuntime():
            return _restart(state, notebook)
        case StopRuntime():
            return _stop(state, notebook)
        case Attach():
            return _attach(state, notebook, change.attachment)
        case Detach():
            return _detach(state, notebook, change.attachment_id)
        case ExecuteCode():
            return _execute(state, notebook, change)
        case ExecutionStarted():
            return _execution(
                state,
                notebook,
                change.execution_id,
                lambda e: (
                    replace(e, lifecycle=Executing(change.at))
                    if isinstance(e.lifecycle, Queued)
                    else e
                ),
            )
        case ExecutionShown():
            return _execution(
                state,
                notebook,
                change.execution_id,
                lambda e: e if e.final else replace(e, output=change.output),
            )
        case ExecutionPrinted():
            return _execution(
                state,
                notebook,
                change.execution_id,
                lambda e: (
                    e
                    if e.final
                    else replace(e, console=(*e.console, change.line))
                ),
            )
        case ExecutionEnded():
            return _execution(
                state,
                notebook,
                change.execution_id,
                lambda e: (
                    e
                    if e.final
                    else replace(
                        e,
                        lifecycle=Finished(
                            change.status,
                            change.at,
                            e.started_at,
                            change.errors,
                        ),
                    )
                ),
            )
        case ExecutionForgotten():
            execution = notebook.executions.get(change.execution_id)
            if execution is None or not execution.final:
                return Outcome(state)
            executions = {
                other: e
                for other, e in notebook.executions.items()
                if other != change.execution_id
            }
            return Outcome(
                state.with_notebook(replace(notebook, executions=executions))
            )
        case _:
            assert_never(change)


# Runtimes


def _from_kernel(
    state: HostState, report: StartupProgress | KernelReady | KernelExited
) -> Outcome:
    located = state.locate(report.runtime_id)
    if located is None:
        # A report about a runtime that has already left the state.
        return Outcome(state)
    notebook, runtime = located
    if report.generation != runtime.generation:
        # A kernel from before a restart, reporting late. Its runtime has
        # moved on, and nothing it says applies to the new kernel.
        return Outcome(state)

    match report:
        case StartupProgress():
            if not isinstance(runtime.lifecycle, Starting):
                return Outcome(state)
            return Outcome(
                state.with_runtime(
                    notebook,
                    replace(runtime, lifecycle=Starting(report.message)),
                )
            )
        case KernelReady():
            if not isinstance(runtime.lifecycle, Starting):
                # The kernel came up just as it was being stopped. It is
                # still going to exit, so the runtime stays terminating.
                return Outcome(state)
            return Outcome(
                state.with_runtime(
                    notebook,
                    replace(
                        runtime,
                        lifecycle=Running(),
                        marimo_version=report.marimo_version,
                    ),
                )
            )
        case KernelExited():
            match runtime.lifecycle:
                case Terminating():
                    ended = _without_executions(notebook)
                    return Outcome(state.with_runtime(ended, None))
                case Starting() | Running():
                    ended = _without_executions(notebook)
                    return Outcome(
                        state.with_runtime(
                            ended,
                            replace(runtime, lifecycle=Failed(report.reason)),
                        )
                    )
                case Failed():
                    return Outcome(state)
                case _:
                    assert_never(runtime.lifecycle)
        case _:
            assert_never(report)


def _start(
    state: HostState, notebook: Notebook, command: StartRuntime
) -> Outcome:
    if notebook.runtime is not None:
        # Whatever state it is in, the notebook has a runtime, and the
        # client gets that one back.
        return Outcome(state)
    if state.locate(command.runtime_id) is not None:
        # Reports name a runtime by id alone, so one id is one runtime.
        raise Conflict(
            f"Runtime {command.runtime_id} belongs to another notebook"
        )
    runtime = Runtime(
        id=command.runtime_id,
        started_at=command.started_at,
        sandbox=command.sandbox,
    )
    return Outcome(
        state.with_runtime(notebook, runtime),
        (_start_kernel(notebook, runtime),),
    )


def _restart(state: HostState, notebook: Notebook) -> Outcome:
    runtime = notebook.runtime
    if runtime is None:
        raise NoRuntime("The notebook has no runtime")
    if not isinstance(runtime.lifecycle, Running):
        raise Conflict("Only a running runtime can restart")

    # The version is cleared because the next kernel may run a different
    # one, as when a sandbox resolves new dependencies.
    next_generation = replace(
        runtime,
        generation=runtime.generation + 1,
        marimo_version=None,
        lifecycle=Starting(),
    )
    return Outcome(
        state.with_runtime(_without_executions(notebook), next_generation),
        (
            StopKernel(runtime.id, runtime.generation),
            _start_kernel(notebook, next_generation),
        ),
    )


def _stop(state: HostState, notebook: Notebook) -> Outcome:
    runtime = notebook.runtime
    if runtime is None:
        raise NoRuntime("The notebook has no runtime")
    match runtime.lifecycle:
        case Terminating():
            return Outcome(state)
        case Failed():
            # No kernel to wait for, so the runtime leaves at once.
            return Outcome(
                state.with_runtime(_without_executions(notebook), None)
            )
        case Starting() | Running():
            return Outcome(
                state.with_runtime(
                    _without_executions(notebook),
                    replace(runtime, lifecycle=Terminating()),
                ),
                (StopKernel(runtime.id, runtime.generation),),
            )
        case _:
            assert_never(runtime.lifecycle)


def _without_executions(notebook: Notebook) -> Notebook:
    """The notebook with its executions forgotten, as when its kernel goes."""
    return replace(notebook, executions={})


def _start_kernel(notebook: Notebook, runtime: Runtime) -> StartKernel:
    return StartKernel(
        notebook_id=notebook.id,
        runtime_id=runtime.id,
        generation=runtime.generation,
        sandbox=runtime.sandbox,
    )


# Attachments


def _attach(
    state: HostState, notebook: Notebook, attachment: Attachment
) -> Outcome:
    if attachment.id in notebook.attachments:
        raise Conflict(f"Attachment {attachment.id} is already connected")
    attachments = {**notebook.attachments, attachment.id: attachment}
    return Outcome(
        state.with_notebook(replace(notebook, attachments=attachments))
    )


def _detach(
    state: HostState, notebook: Notebook, attachment_id: AttachmentId
) -> Outcome:
    if attachment_id not in notebook.attachments:
        return Outcome(state)
    attachments = {
        other: attachment
        for other, attachment in notebook.attachments.items()
        if other != attachment_id
    }
    return Outcome(
        state.with_notebook(replace(notebook, attachments=attachments))
    )


# Executions


def _execute(
    state: HostState, notebook: Notebook, command: ExecuteCode
) -> Outcome:
    runtime = notebook.runtime
    if runtime is None:
        raise NoRuntime("The notebook has no runtime")
    if not isinstance(runtime.lifecycle, Running):
        raise Conflict("The runtime is not running")
    if notebook.running_execution() is not None:
        raise Conflict("The notebook has an execution in progress")
    if command.execution_id in notebook.executions:
        raise Conflict(f"Execution {command.execution_id} already happened")
    execution = Execution(id=command.execution_id, code=command.code)
    executions = {**notebook.executions, execution.id: execution}
    return Outcome(
        state.with_notebook(replace(notebook, executions=executions))
    )


def _execution(
    state: HostState,
    notebook: Notebook,
    execution_id: ExecutionId,
    update: Callable[[Execution], Execution],
) -> Outcome:
    execution = notebook.executions.get(execution_id)
    if execution is None:
        return Outcome(state)
    updated = update(execution)
    if updated == execution:
        return Outcome(state)
    executions = {**notebook.executions, execution_id: updated}
    return Outcome(
        state.with_notebook(replace(notebook, executions=executions))
    )


# The workspace


def _notebook_seen(state: HostState, notebook: Notebook) -> Outcome:
    current = state.notebooks.get(notebook.id)
    if current is None:
        return Outcome(state.with_notebook(notebook))
    seen = replace(
        current,
        title=notebook.title,
        path=notebook.path,
        updated_at=notebook.updated_at,
        project_id=notebook.project_id,
    )
    if seen == current:
        return Outcome(state)
    return Outcome(state.with_notebook(seen))


def _notebook_gone(state: HostState, notebook_id: NotebookId) -> Outcome:
    current = state.notebooks.get(notebook_id)
    if current is None:
        return Outcome(state)
    # Without a file the notebook stays only while something refers to
    # it, nameless; `with_notebook` lets it go otherwise.
    gone = replace(current, path=None, updated_at=None)
    if gone == current:
        return Outcome(state)
    return Outcome(state.with_notebook(gone))
