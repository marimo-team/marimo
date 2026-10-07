# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from marimo._host.model import (
    Attachment,
    ConsoleLine,
    Display,
    Failed,
    HostState,
    Indexed,
    Notebook,
    Project,
    Running,
    Runtime,
    Starting,
    Terminating,
)
from marimo._host.transitions import (
    Attach,
    Conflict,
    Detach,
    ExecuteCode,
    ExecutionEnded,
    ExecutionForgotten,
    ExecutionPrinted,
    ExecutionShown,
    ExecutionStarted,
    KernelExited,
    KernelReady,
    NoRuntime,
    NotebookGone,
    NotebookSeen,
    NotFound,
    Outcome,
    RestartRuntime,
    StartKernel,
    StartRuntime,
    StartupProgress,
    StopKernel,
    StopRuntime,
    apply,
)
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
OTHER = RuntimeId("r2")
EXECUTION = ExecutionId("e1")


def empty_host() -> HostState:
    project = Project(
        PROJECT, "forecasting", Path("/Users/me/forecasting"), Indexed()
    )
    notebook = Notebook(
        NOTEBOOK, PROJECT, "forecasts", Path("forecasts.py"), NOW
    )
    return HostState().with_project(project).with_notebook(notebook)


def starting_host() -> HostState:
    start = StartRuntime(NOTEBOOK, RUNTIME, NOW, sandbox=False)
    return apply(empty_host(), start).state


def running_host() -> HostState:
    return apply(starting_host(), KernelReady(RUNTIME, 0, "0.25.0")).state


def failed_host() -> HostState:
    return apply(running_host(), KernelExited(RUNTIME, 0, "segfault")).state


def notebook_of(state: HostState) -> Notebook:
    return state.notebooks[NOTEBOOK]


def runtime_of(state: HostState) -> Runtime:
    runtime = notebook_of(state).runtime
    assert runtime is not None
    return runtime


def attachment(attachment_id: str = "a1") -> Attachment:
    return Attachment(AttachmentId(attachment_id), "browser", "Chrome", NOW)


# Runtimes


def test_start_creates_a_starting_runtime_and_launches_its_kernel() -> None:
    start = StartRuntime(NOTEBOOK, RUNTIME, NOW, sandbox=True)
    outcome = apply(empty_host(), start)

    assert runtime_of(outcome.state) == Runtime(RUNTIME, NOW, sandbox=True)
    assert runtime_of(outcome.state).lifecycle == Starting()
    assert outcome.actions == (
        StartKernel(NOTEBOOK, RUNTIME, generation=0, sandbox=True),
    )


def test_start_leaves_an_existing_runtime_alone_whatever_its_state() -> None:
    start = StartRuntime(NOTEBOOK, OTHER, NOW, sandbox=False)
    for state in (starting_host(), running_host(), failed_host()):
        assert apply(state, start) == Outcome(state)


def test_start_refuses_a_runtime_id_another_notebook_holds() -> None:
    other = Notebook(NotebookId("n2"), PROJECT, "other", Path("other.py"), NOW)
    state = running_host().with_notebook(other)
    start = StartRuntime(other.id, RUNTIME, NOW, sandbox=False)
    with pytest.raises(Conflict, match="another notebook"):
        apply(state, start)


def test_kernel_ready_moves_to_running_and_records_the_version() -> None:
    outcome = apply(starting_host(), KernelReady(RUNTIME, 0, "0.25.0"))

    assert runtime_of(outcome.state).lifecycle == Running()
    assert runtime_of(outcome.state).marimo_version == "0.25.0"
    assert outcome.actions == ()


def test_startup_progress_shows_only_while_starting() -> None:
    progress = StartupProgress(RUNTIME, 0, "Preparing environment")

    shown = apply(starting_host(), progress).state
    assert runtime_of(shown).lifecycle == Starting("Preparing environment")

    running = running_host()
    assert apply(running, progress) == Outcome(running)


def test_unexpected_exit_fails_the_runtime_and_keeps_attachments() -> None:
    attached = apply(running_host(), Attach(NOTEBOOK, attachment())).state
    outcome = apply(attached, KernelExited(RUNTIME, 0, "segfault"))

    assert runtime_of(outcome.state).lifecycle == Failed("segfault")
    assert list(notebook_of(outcome.state).attachments) == ["a1"]
    assert outcome.actions == ()

    # A failed runtime hears nothing more from its kernel.
    failed = outcome.state
    for report in (
        KernelExited(RUNTIME, 0, "again"),
        KernelReady(RUNTIME, 0, "0.25.0"),
        StartupProgress(RUNTIME, 0, "late"),
    ):
        assert apply(failed, report) == Outcome(failed)


def test_restart_stops_the_old_kernel_and_starts_the_next_generation() -> None:
    attached = apply(running_host(), Attach(NOTEBOOK, attachment())).state
    outcome = apply(attached, RestartRuntime(NOTEBOOK))
    runtime = runtime_of(outcome.state)

    assert runtime.id == RUNTIME
    assert runtime.generation == 1
    assert runtime.lifecycle == Starting()
    assert runtime.marimo_version is None
    assert runtime.started_at == NOW
    assert list(notebook_of(outcome.state).attachments) == ["a1"]
    assert outcome.actions == (
        StopKernel(RUNTIME, generation=0),
        StartKernel(NOTEBOOK, RUNTIME, generation=1, sandbox=False),
    )


def test_restart_needs_a_running_runtime() -> None:
    with pytest.raises(NoRuntime):
        apply(empty_host(), RestartRuntime(NOTEBOOK))
    for state in (starting_host(), failed_host()):
        with pytest.raises(Conflict):
            apply(state, RestartRuntime(NOTEBOOK))


def test_reports_from_an_earlier_generation_are_ignored() -> None:
    restarted = apply(running_host(), RestartRuntime(NOTEBOOK)).state

    # The old kernel exits after the restart began; the new one must not
    # be marked failed, nor running, on its account.
    late_exit = KernelExited(RUNTIME, 0, "killed")
    late_ready = KernelReady(RUNTIME, 0, "0.25.0")
    assert apply(restarted, late_exit) == Outcome(restarted)
    assert apply(restarted, late_ready) == Outcome(restarted)

    ready = apply(restarted, KernelReady(RUNTIME, 1, "0.25.0")).state
    assert runtime_of(ready).lifecycle == Running()


def test_stop_while_starting_waits_for_the_kernel_to_exit() -> None:
    outcome = apply(starting_host(), StopRuntime(NOTEBOOK))
    terminating = outcome.state

    assert runtime_of(terminating).lifecycle == Terminating()
    assert outcome.actions == (StopKernel(RUNTIME, generation=0),)

    # The kernel came up just as it was told to stop; it must not come back.
    came_up = KernelReady(RUNTIME, 0, "0.25.0")
    assert apply(terminating, came_up) == Outcome(terminating)

    gone = apply(terminating, KernelExited(RUNTIME, 0, "stopped"))
    assert notebook_of(gone.state).runtime is None
    assert gone.actions == ()


def test_stop_removes_a_failed_runtime_at_once_and_needs_one() -> None:
    outcome = apply(failed_host(), StopRuntime(NOTEBOOK))
    assert notebook_of(outcome.state).runtime is None
    assert outcome.actions == ()

    terminating = apply(running_host(), StopRuntime(NOTEBOOK)).state
    assert apply(terminating, StopRuntime(NOTEBOOK)) == Outcome(terminating)

    with pytest.raises(NoRuntime):
        apply(empty_host(), StopRuntime(NOTEBOOK))


def test_unknown_runtime_reports_are_ignored_and_commands_refused() -> None:
    state = empty_host()
    assert apply(state, KernelExited(OTHER, 0, "late")) == Outcome(state)
    missing = NotebookId("missing")
    with pytest.raises(NotFound):
        apply(state, StopRuntime(missing))
    with pytest.raises(NotFound):
        apply(state, StartRuntime(missing, RUNTIME, NOW, sandbox=False))


# Attachments


def test_attachments_belong_to_the_notebook_not_the_runtime() -> None:
    attached = apply(empty_host(), Attach(NOTEBOOK, attachment())).state
    assert list(notebook_of(attached).attachments) == ["a1"]

    started = apply(
        attached, StartRuntime(NOTEBOOK, RUNTIME, NOW, sandbox=False)
    ).state
    stopped = apply(started, StopRuntime(NOTEBOOK)).state
    gone = apply(stopped, KernelExited(RUNTIME, 0, "stopped")).state
    assert notebook_of(gone).runtime is None
    assert list(notebook_of(gone).attachments) == ["a1"]

    with pytest.raises(Conflict):
        apply(attached, Attach(NOTEBOOK, attachment()))

    detached = apply(attached, Detach(NOTEBOOK, AttachmentId("a1"))).state
    assert notebook_of(detached).attachments == {}
    assert apply(detached, Detach(NOTEBOOK, AttachmentId("a1"))) == Outcome(
        detached
    )


# Executions


def test_an_execution_runs_against_a_running_runtime_only() -> None:
    execute = ExecuteCode(NOTEBOOK, EXECUTION, "1 + 1")
    with pytest.raises(NoRuntime):
        apply(empty_host(), execute)
    with pytest.raises(Conflict):
        apply(starting_host(), execute)

    queued = apply(running_host(), execute).state
    execution = notebook_of(queued).executions[EXECUTION]
    assert execution.status == "queued"
    assert execution.code == "1 + 1"

    # One at a time, and never the same key twice.
    with pytest.raises(Conflict):
        apply(queued, ExecuteCode(NOTEBOOK, ExecutionId("e2"), "2"))
    done = apply(
        queued, ExecutionEnded(NOTEBOOK, EXECUTION, "succeeded", (), NOW)
    ).state
    # Ended without the kernel ever starting it: no start time to invent.
    assert notebook_of(done).executions[EXECUTION].started_at is None
    with pytest.raises(Conflict):
        apply(done, execute)
    second = apply(done, ExecuteCode(NOTEBOOK, ExecutionId("e2"), "2")).state
    assert list(notebook_of(second).executions) == ["e1", "e2"]


def test_an_execution_records_its_progress_until_it_is_final() -> None:
    queued = apply(
        running_host(), ExecuteCode(NOTEBOOK, EXECUTION, "print(1)")
    ).state
    later = NOW.replace(second=5)

    started = apply(queued, ExecutionStarted(NOTEBOOK, EXECUTION, NOW)).state
    printed = apply(
        started,
        ExecutionPrinted(NOTEBOOK, EXECUTION, ConsoleLine("stdout", "1\n")),
    ).state
    shown = apply(
        printed,
        ExecutionShown(NOTEBOOK, EXECUTION, Display("text/plain", "1")),
    ).state
    ended = apply(
        shown, ExecutionEnded(NOTEBOOK, EXECUTION, "succeeded", (), later)
    ).state

    execution = notebook_of(ended).executions[EXECUTION]
    assert execution.status == "succeeded"
    assert execution.started_at == NOW
    assert execution.completed_at == later
    assert execution.console == (ConsoleLine("stdout", "1\n"),)
    assert execution.output == Display("text/plain", "1")

    # Final means final: later reports change nothing.
    for late in (
        ExecutionShown(NOTEBOOK, EXECUTION, Display("text/plain", "2")),
        ExecutionPrinted(NOTEBOOK, EXECUTION, ConsoleLine("stderr", "!")),
        ExecutionEnded(NOTEBOOK, EXECUTION, "failed", (), later),
        ExecutionStarted(NOTEBOOK, EXECUTION, later),
    ):
        assert apply(ended, late) == Outcome(ended)

    forgotten = apply(ended, ExecutionForgotten(NOTEBOOK, EXECUTION)).state
    assert notebook_of(forgotten).executions == {}
    # A run in flight is not forgotten.
    assert apply(shown, ExecutionForgotten(NOTEBOOK, EXECUTION)) == Outcome(
        shown
    )


def test_stopping_or_restarting_the_runtime_drops_its_executions() -> None:
    queued = apply(
        running_host(), ExecuteCode(NOTEBOOK, EXECUTION, "sleep")
    ).state

    restarted = apply(queued, RestartRuntime(NOTEBOOK)).state
    assert notebook_of(restarted).executions == {}

    stopped = apply(queued, StopRuntime(NOTEBOOK)).state
    assert notebook_of(stopped).executions == {}

    crashed = apply(queued, KernelExited(RUNTIME, 0, "segfault")).state
    assert notebook_of(crashed).executions == {}
    assert runtime_of(crashed).lifecycle == Failed("segfault")


# The workspace


def test_a_seen_notebook_keeps_what_the_host_already_holds() -> None:
    running = running_host()
    rescanned = Notebook(
        NOTEBOOK, PROJECT, "forecasts (renamed)", Path("forecasts.py"), NOW
    )

    outcome = apply(running, NotebookSeen(rescanned))

    assert notebook_of(outcome.state).title == "forecasts (renamed)"
    assert runtime_of(outcome.state) == runtime_of(running)
    assert apply(outcome.state, NotebookSeen(rescanned)) == Outcome(
        outcome.state
    )


def test_a_gone_notebook_is_removed_unless_something_refers_to_it() -> None:
    gone = apply(empty_host(), NotebookGone(NOTEBOOK)).state
    assert NOTEBOOK not in gone.notebooks

    nameless = apply(running_host(), NotebookGone(NOTEBOOK)).state
    notebook = notebook_of(nameless)
    assert notebook.path is None
    assert notebook.updated_at is None
    assert notebook.runtime is not None
    assert apply(nameless, NotebookGone(NOTEBOOK)) == Outcome(nameless)

    # When the runtime leaves too, so does the notebook.
    stopping = apply(nameless, StopRuntime(NOTEBOOK)).state
    released = apply(stopping, KernelExited(RUNTIME, 0, "stopped")).state
    assert NOTEBOOK not in released.notebooks

    # An attachment alone also keeps it; the last detach lets it go.
    attached = apply(empty_host(), Attach(NOTEBOOK, attachment())).state
    kept = apply(attached, NotebookGone(NOTEBOOK)).state
    assert notebook_of(kept).path is None
    released = apply(kept, Detach(NOTEBOOK, AttachmentId("a1"))).state
    assert NOTEBOOK not in released.notebooks

    unknown = NotebookGone(NotebookId("missing"))
    assert apply(empty_host(), unknown) == Outcome(empty_host())
