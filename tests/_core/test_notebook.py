# Copyright 2026 Marimo. All rights reserved.
"""Notebook commands and state updates from backend messages."""

from __future__ import annotations

import pytest
from dirty_equals import IsDatetime
from inline_snapshot import snapshot
from msgspec import UNSET

from marimo._core import backend as be
from marimo._core.errors import Conflict, NoRuntime, NotFound
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.protocol import (
    Console,
    ConsoleMessage,
    DisplayData,
    Error,
    ErrorOutcome,
    Execution,
    ExecutionId,
    ExecutionMessage,
    InterruptedOutcome,
    ItemId,
    NotebookId,
    Run,
    RunId,
    RunMessage,
    RunOutcome,
    Runtime,
    ValueOutcome,
)
from marimo._core.stream import Event
from tests._core.conftest import ScriptedBackend, names, request_ids


def running(notebook: Notebook, backend: ScriptedBackend) -> Runtime:
    notebook.start(request_id="req-start")
    notebook.observe(be.Running(marimo_version="0.25.0"))
    backend.calls.clear()
    assert notebook.runtime is not None
    return notebook.runtime


def scratch(notebook: Notebook, run_id: str = "run-1") -> Run:
    run = notebook.run("3 * 3", request_id=run_id)
    notebook.observe(
        be.Planned(
            run.id,
            (be.PlannedExecution(ExecutionId("e1"), None, "9f", "3 * 3"),),
        )
    )
    notebook.observe(be.Status(ExecutionId("e1"), "running"))
    return run


class TestStart:
    def test_starts_a_runtime_and_asks_the_backend(
        self, notebook: Notebook, backend: ScriptedBackend, log: list[Event]
    ) -> None:
        runtime, created = notebook.start(request_id="req-1")

        assert created
        assert runtime.status == "starting"
        assert backend.calls == [("start", runtime.id)]
        assert names(log) == ["runtime"]
        assert request_ids(log) == ["req-1"]

    def test_returns_an_existing_runtime_without_starting(
        self, notebook: Notebook, backend: ScriptedBackend, log: list[Event]
    ) -> None:
        first, _ = notebook.start()
        again, created = notebook.start()

        assert not created
        assert again == first
        assert backend.calls == [("start", first.id)]
        assert names(log) == ["runtime"]

    def test_request_follows_the_runtime_until_it_settles(
        self, notebook: Notebook, log: list[Event]
    ) -> None:
        notebook.start(request_id="req-1")
        notebook.observe(be.Starting("Preparing the environment"))
        notebook.observe(be.Running(marimo_version="0.25.0"))
        notebook.attach()

        assert names(log) == ["runtime", "runtime", "runtime", "attachment"]
        assert request_ids(log) == ["req-1", "req-1", "req-1", UNSET]
        assert notebook.runtime is not None
        assert notebook.runtime.status == "running"
        assert notebook.runtime.marimo_version == "0.25.0"
        assert notebook.runtime.message is None

    def test_a_kernel_that_never_comes_up_fails(
        self, notebook: Notebook, log: list[Event]
    ) -> None:
        notebook.start(request_id="req-1")
        notebook.observe(be.Exited("No such environment"))

        assert notebook.runtime is not None
        assert notebook.runtime.status == "failed"
        assert notebook.runtime.message == "No such environment"
        assert request_ids(log) == ["req-1", "req-1"]


class TestStop:
    def test_stop_cancels_a_pending_restart(
        self, notebook: Notebook, backend: ScriptedBackend, log: list[Event]
    ) -> None:
        running(notebook, backend)
        notebook.restart(request_id="restart")
        notebook.stop(request_id="stop")
        log.clear()

        notebook.observe(be.Exited())

        assert notebook.runtime is None
        assert backend.calls == [("stop",)]
        assert names(log) == ["runtime.removed"]
        assert request_ids(log) == ["stop"]

    def test_needs_a_runtime(self, notebook: Notebook) -> None:
        with pytest.raises(NoRuntime):
            notebook.stop()

    def test_terminates_then_removes_once_the_kernel_is_gone(
        self, notebook: Notebook, backend: ScriptedBackend, log: list[Event]
    ) -> None:
        running(notebook, backend)
        log.clear()

        runtime = notebook.stop(request_id="req-stop")
        assert runtime.status == "terminating"
        assert backend.calls == [("stop",)]

        notebook.observe(be.Exited("Stopped"))
        assert notebook.runtime is None
        assert names(log) == ["runtime", "runtime.removed"]
        assert request_ids(log) == ["req-stop", "req-stop"]

    def test_ends_runs_in_flight_and_retains_results(
        self,
        host: Host,
        notebook: Notebook,
        backend: ScriptedBackend,
        log: list[Event],
    ) -> None:
        running(notebook, backend)
        scratch(notebook)
        notebook.observe(be.Produced(console("o1", "e1", "hi\n")))
        log.clear()

        notebook.stop()
        notebook.observe(be.Exited())

        assert names(log) == [
            "runtime",
            "execution",
            "run",
            "runtime.removed",
        ]
        interrupted = log[1].data
        assert isinstance(interrupted, ExecutionMessage)
        assert interrupted.execution.status == "completed"
        assert isinstance(interrupted.execution.outcome, InterruptedOutcome)
        assert names(host.events(notebook_id=notebook.id)) == [
            "notebook",
            "run",
            "execution",
            "console",
            "ready",
        ]

    def test_a_failed_runtime_is_removed_at_once(
        self, notebook: Notebook, backend: ScriptedBackend, log: list[Event]
    ) -> None:
        notebook.start()
        notebook.observe(be.Exited("boom"))
        backend.calls.clear()
        log.clear()

        terminating = notebook.stop()

        assert terminating.status == "terminating"
        assert notebook.runtime is None
        assert backend.calls == []
        assert names(log) == ["runtime", "runtime.removed"]

    def test_keeps_completed_results_when_stopped(
        self,
        host: Host,
        notebook: Notebook,
        backend: ScriptedBackend,
        log: list[Event],
    ) -> None:
        running(notebook, backend)
        scratch(notebook)
        notebook.observe(be.Produced(console("o1", "e1", "x")))
        notebook.observe(be.Concluded(ExecutionId("e1"), value("")))
        notebook.observe(be.Status(ExecutionId("e1"), "completed"))
        notebook.observe(be.Done(RunId("run-1"), "succeeded"))
        log.clear()

        notebook.stop(request_id="stop")
        notebook.observe(be.Exited())

        assert names(log) == [
            "runtime",
            "runtime.removed",
        ]
        assert request_ids(log) == ["stop", "stop"]
        assert names(host.events(notebook_id=notebook.id)) == [
            "notebook",
            "run",
            "execution",
            "console",
            "ready",
        ]


class TestRestart:
    def test_only_a_running_runtime_restarts(self, notebook: Notebook) -> None:
        with pytest.raises(NoRuntime):
            notebook.restart()
        notebook.start()
        with pytest.raises(Conflict):
            notebook.restart()

    def test_replaces_the_runtime_and_keeps_old_results(
        self, notebook: Notebook, backend: ScriptedBackend, log: list[Event]
    ) -> None:
        before = running(notebook, backend)
        scratch(notebook)
        backend.calls.clear()
        log.clear()

        response = notebook.restart(request_id="req-restart")
        assert response.id != before.id
        assert response.status == "starting"
        assert notebook.runtime is not None
        assert notebook.runtime.id == before.id
        assert notebook.runtime.status == "terminating"
        assert backend.calls == [("stop",)]
        notebook.observe(be.Exited())
        assert notebook.runtime is not None
        assert notebook.runtime.id == response.id
        assert backend.calls == [("stop",), ("start", notebook.runtime.id)]
        notebook.observe(be.Running(marimo_version="0.25.0"))

        after = notebook.runtime
        assert after is not None
        assert after.id != before.id
        assert after.status == "running"
        assert after.started_at >= before.started_at
        assert names(log) == [
            "runtime",
            "execution",
            "run",
            "runtime.removed",
            "runtime",
            "runtime",
        ]
        execution = log[1].data
        assert isinstance(execution, ExecutionMessage)
        assert execution.execution.runtime_id == before.id
        assert request_ids(log)[0] == "req-restart"
        assert request_ids(log)[-1] == "req-restart"


class TestAdoption:
    @pytest.mark.parametrize("reports_starting", [False, True])
    def test_external_relaunch_recovers_a_failed_runtime(
        self,
        notebook: Notebook,
        backend: ScriptedBackend,
        host: Host,
        reports_starting: bool,
    ) -> None:
        before = running(notebook, backend)
        scratch(notebook)
        notebook.observe(be.Exited("Kernel exited"))
        backend.calls.clear()

        if reports_starting:
            notebook.observe(be.Starting("Relaunching"))
        notebook.observe(be.Running("0.26.0"))

        assert notebook.runtime is not None
        assert notebook.runtime.id != before.id
        assert notebook.runtime.marimo_version == "0.26.0"
        assert names(host.events(notebook_id=notebook.id)) == [
            "notebook",
            "runtime",
            "run",
            "execution",
            "ready",
        ]
        assert backend.calls == []
        notebook.run("1", request_id="after-relaunch")
        assert backend.calls == [("run", "after-relaunch", "1")]

    def test_a_kernel_someone_else_started_is_published(
        self, notebook: Notebook, backend: ScriptedBackend, log: list[Event]
    ) -> None:
        notebook.observe(be.Starting("Starting the kernel"))
        notebook.observe(be.Running(marimo_version="0.25.0"))

        assert backend.calls == []
        assert notebook.runtime is not None
        assert notebook.runtime.status == "running"
        assert names(log) == ["runtime", "runtime"]

    def test_a_kernel_that_dies_on_its_own_fails_and_keeps_results(
        self,
        host: Host,
        notebook: Notebook,
        backend: ScriptedBackend,
        log: list[Event],
    ) -> None:
        running(notebook, backend)
        scratch(notebook)
        log.clear()

        notebook.observe(be.Exited("killed"))

        assert notebook.runtime is not None
        assert notebook.runtime.status == "failed"
        assert notebook.runtime.message == "killed"
        assert names(log) == ["execution", "run", "runtime"]
        [run] = [
            event.data.run
            for event in host.events(notebook_id=notebook.id)
            if isinstance(event.data, RunMessage)
        ]
        assert run.status == "completed"


def console(
    item_id: str, execution_id: str, text: str, seq: int = 0
) -> Console:
    return Console(
        id=ItemId(item_id),
        execution_id=ExecutionId(execution_id),
        seq=seq,
        name="stdout",
        text=text,
    )


def value(data: str) -> ValueOutcome:
    return ValueOutcome(display=DisplayData(mimetype="text/html", data=data))


class TestRun:
    def test_run_filter_preserves_output_ownership_and_replay(
        self, host: Host, notebook: Notebook, backend: ScriptedBackend
    ) -> None:
        running(notebook, backend)
        run = scratch(notebook)
        notebook.observe(be.Concluded(ExecutionId("e1"), value("9")))
        notebook.observe(be.Status(ExecutionId("e1"), "completed"))
        notebook.observe(be.Done(run.id, "succeeded"))
        cursor = host.events()[-1].id
        live: list[Event] = []
        unsubscribe = host.subscribe(
            live.append, notebook_id=notebook.id, run_id=run.id
        )

        notebook.run("2", request_id="next")
        notebook.attach()
        # Output can arrive after completed and while another run is active.
        notebook.observe(be.Produced(console("late", "e1", "background")))
        assert names(live) == ["console"]
        assert names(
            host.events(cursor, notebook_id=notebook.id, run_id=run.id)
        ) == ["console", "ready"]
        assert names(host.events(notebook_id=notebook.id, run_id=run.id)) == [
            "run",
            "execution",
            "console",
            "ready",
        ]
        assert names(
            host.events(
                notebook_id=notebook.id, run_id=run.id, types={"console"}
            )
        ) == ["console", "ready"]

        host.remove_notebook(notebook.id)
        assert names(live) == [
            "console",
            "console.removed",
            "execution.removed",
            "run.removed",
        ]
        unsubscribe()

    def test_needs_a_running_runtime(self, notebook: Notebook) -> None:
        with pytest.raises(NoRuntime):
            notebook.run("1", request_id="r")
        notebook.start()
        with pytest.raises(Conflict, match="starting"):
            notebook.run("1", request_id="r")

    def test_a_scratch_run_from_queued_to_completed(
        self,
        host: Host,
        notebook: Notebook,
        backend: ScriptedBackend,
        log: list[Event],
    ) -> None:
        running(notebook, backend)
        log.clear()
        key = "7c1e9a3f"

        run = notebook.run("3 * 3", request_id=key)
        assert run.started_at is None

        notebook.observe(
            be.Planned(
                run.id,
                (be.PlannedExecution(ExecutionId("e7"), None, "9f", "3 * 3"),),
            )
        )
        notebook.observe(be.Status(ExecutionId("e7"), "running"))
        notebook.observe(be.Concluded(ExecutionId("e7"), value("working")))
        notebook.observe(be.Produced(console("o3", "e7", "2\n")))
        notebook.observe(
            be.Concluded(ExecutionId("e7"), value("working<pre>9</pre>"))
        )
        notebook.observe(be.Status(ExecutionId("e7"), "completed"))
        notebook.observe(be.Done(run.id, "succeeded"))

        assert notebook.runtime is not None
        assert backend.calls == [("run", key, "3 * 3")]
        assert names(log) == [
            "run",
            "execution",
            "run",
            "execution",
            "execution",
            "console",
            "execution",
            "execution",
            "run",
        ]
        assert set(request_ids(log)) == {key}
        runs = [
            data.run
            for event in log
            if isinstance(data := event.data, RunMessage)
        ]
        executions = [
            data.execution
            for event in log
            if isinstance(data := event.data, ExecutionMessage)
        ]
        consoles = [
            data.console
            for event in log
            if isinstance(data := event.data, ConsoleMessage)
        ]
        assert [run.status for run in runs] == [
            "queued",
            "running",
            "completed",
        ]
        assert [(e.status, e.outcome) for e in executions] == [
            ("queued", None),
            ("running", None),
            ("running", value("working")),
            ("running", value("working<pre>9</pre>")),
            ("completed", value("working<pre>9</pre>")),
        ]
        retained = [
            event.data
            for event in host.events(notebook_id=notebook.id)
            if event.kind in {"run", "execution", "console"}
        ]
        assert retained == [
            RunMessage(run=runs[-1]),
            ExecutionMessage(execution=executions[-1]),
            *(ConsoleMessage(console=item) for item in consoles),
        ]
        assert [runs[-1], executions[-1], *consoles] == snapshot(
            [
                Run(
                    caused_by=None,
                    completed_at=IsDatetime(),
                    id=RunId("7c1e9a3f"),
                    notebook_id=NotebookId("n1"),
                    outcome="succeeded",
                    started_at=IsDatetime(),
                    status="completed",
                ),
                Execution(
                    caused_by=None,
                    cell_id=None,
                    code="3 * 3",
                    code_hash="9f",
                    completed_at=IsDatetime(),
                    bindings=[],
                    id=ExecutionId("e7"),
                    outcome=ValueOutcome(
                        display=DisplayData(
                            data="working<pre>9</pre>", mimetype="text/html"
                        )
                    ),
                    run_id=RunId("7c1e9a3f"),
                    runtime_id=notebook.runtime.id,
                    stale=None,
                    started_at=IsDatetime(),
                    status="completed",
                ),
                Console(
                    execution_id=ExecutionId("e7"),
                    id=ItemId("o3"),
                    name="stdout",
                    seq=0,
                    text="2\n",
                ),
            ]
        )

    def test_repeating_the_request_returns_the_same_run(
        self, notebook: Notebook, backend: ScriptedBackend
    ) -> None:
        running(notebook, backend)
        first = notebook.run("1", request_id="same")
        assert notebook.run("1", request_id="same") == first
        assert backend.calls == [("run", "same", "1")]

    def test_one_run_at_a_time(
        self, notebook: Notebook, backend: ScriptedBackend, log: list[Event]
    ) -> None:
        running(notebook, backend)
        notebook.run("1", request_id="first")
        with pytest.raises(Conflict, match="first"):
            notebook.run("2", request_id="second")
        notebook.observe(be.Done(RunId("first"), "succeeded"))
        final = log[-1].data
        assert isinstance(final, RunMessage)
        assert final.run.status == "completed"
        assert final.run.started_at is None
        assert final.run.completed_at is not None
        assert notebook.run("2", request_id="second").status == "queued"

    def test_an_item_replaces_itself_by_id(
        self, host: Host, notebook: Notebook, backend: ScriptedBackend
    ) -> None:
        running(notebook, backend)
        scratch(notebook)
        notebook.observe(be.Produced(console("o1", "e1", "0\n")))
        notebook.observe(be.Produced(console("o1", "e1", "0\n1\n")))
        items = [
            event.data.console
            for event in host.events(notebook_id=notebook.id)
            if isinstance(event.data, ConsoleMessage)
        ]
        assert len(items) == 1
        assert isinstance(items[0], Console)
        assert items[0].text == "0\n1\n"

    def test_messages_about_unknown_runs_are_ignored(
        self, notebook: Notebook, backend: ScriptedBackend, log: list[Event]
    ) -> None:
        running(notebook, backend)
        log.clear()
        notebook.observe(
            be.Planned(
                RunId("ghost"),
                (be.PlannedExecution(ExecutionId("e9"), None, "x", "3 * 3"),),
            )
        )
        notebook.observe(be.Status(ExecutionId("e9"), "running"))
        notebook.observe(be.Produced(console("o9", "e9", "boo")))
        notebook.observe(be.Done(RunId("ghost"), "succeeded"))
        assert log == []


class TestRunCompletion:
    def test_later_work_gets_its_own_run(
        self, notebook: Notebook, backend: ScriptedBackend, log: list[Event]
    ) -> None:
        running(notebook, backend)
        original = scratch(notebook)
        notebook.observe(be.Concluded(ExecutionId("e1"), value("9")))
        notebook.observe(be.Status(ExecutionId("e1"), "completed"))
        notebook.observe(be.Done(original.id, "succeeded"))
        log.clear()
        notebook.observe(be.Scheduled(RunId("later"), ExecutionId("e1")))
        notebook.observe(be.Done(RunId("later"), "succeeded"))
        assert request_ids(log) == [UNSET, UNSET]
        assert all(event.run_id == "later" for event in log)
        final = log[-1].data
        assert isinstance(final, RunMessage)
        assert final.run.caused_by == "e1"
        assert (
            notebook.run("3 * 3", request_id=original.id).status == "completed"
        )

    @pytest.mark.parametrize("outcome", ["failed", "interrupted"])
    def test_can_end_before_any_execution(
        self,
        notebook: Notebook,
        backend: ScriptedBackend,
        log: list[Event],
        outcome: RunOutcome,
    ) -> None:
        running(notebook, backend)
        run = notebook.run("pass", request_id="never-started")
        assert run.outcome is None
        notebook.observe(be.Done(run.id, outcome))
        final = log[-1].data
        assert isinstance(final, RunMessage)
        assert final.run.status == "completed"
        assert final.run.outcome == outcome
        assert final.run.started_at is None
        assert final.run.completed_at is not None

    @pytest.mark.parametrize("outcome", ["failed", "interrupted"])
    def test_downstream_work_outlives_the_root_execution(
        self,
        notebook: Notebook,
        backend: ScriptedBackend,
        log: list[Event],
        outcome: RunOutcome,
    ) -> None:
        running(notebook, backend)
        run = scratch(notebook)
        with pytest.raises(ValueError, match="unfinished"):
            notebook.observe(be.Done(run.id, "succeeded"))
        notebook.observe(be.Concluded(ExecutionId("e1"), value("9")))
        notebook.observe(be.Status(ExecutionId("e1"), "completed"))
        notebook.observe(
            be.Planned(
                run.id,
                (
                    be.PlannedExecution(
                        ExecutionId("child"),
                        "cell",
                        "hash",
                        None,
                        ExecutionId("e1"),
                    ),
                ),
            )
        )
        notebook.observe(be.Status(ExecutionId("child"), "running"))
        notebook.observe(
            be.Concluded(
                ExecutionId("child"),
                ErrorOutcome(
                    Error(
                        kind="exception",
                        message="boom",
                        name="RuntimeError",
                        traceback=None,
                        source="marimo",
                        severity="error",
                        range=None,
                        related=[],
                    )
                ),
            )
        )
        notebook.observe(be.Status(ExecutionId("child"), "completed"))
        # Even an empty execution queue is not an authoritative end to scheduling.
        current = notebook.run("3 * 3", request_id=run.id)
        assert current.status == "running"
        assert current.outcome is None
        with pytest.raises(ValueError, match="successful"):
            notebook.observe(be.Done(run.id, "succeeded"))
        notebook.observe(be.Done(run.id, outcome))
        final = log[-1].data
        assert isinstance(final, RunMessage)
        assert final.run.outcome == outcome
        assert final.run.status == "completed"
        log.clear()
        # Final records cannot reopen or acquire executions, but output keeps its origin.
        notebook.observe(be.Status(ExecutionId("e1"), "running"))
        notebook.observe(be.Concluded(ExecutionId("e1"), value("changed")))
        notebook.observe(be.Done(run.id, "succeeded"))
        notebook.observe(
            be.Planned(
                run.id,
                (
                    be.PlannedExecution(
                        ExecutionId("late"), "late-cell", "hash", None
                    ),
                ),
            )
        )
        assert log == []
        notebook.observe(
            be.Produced(console("late-output", "e1", "still owned"))
        )
        assert names(log) == ["console"]


class TestInterrupt:
    def test_asks_the_backend_while_in_progress(
        self, notebook: Notebook, backend: ScriptedBackend
    ) -> None:
        running(notebook, backend)
        scratch(notebook)
        backend.calls.clear()

        notebook.interrupt("run-1")

        assert backend.calls == [("interrupt", "run-1")]

    def test_refuses_unknown_and_finished_runs(
        self, notebook: Notebook, backend: ScriptedBackend
    ) -> None:
        running(notebook, backend)
        with pytest.raises(NotFound):
            notebook.interrupt("nope")
        scratch(notebook)
        notebook.observe(be.Concluded(ExecutionId("e1"), value("9")))
        notebook.observe(be.Status(ExecutionId("e1"), "completed"))
        notebook.observe(be.Done(RunId("run-1"), "succeeded"))
        with pytest.raises(Conflict):
            notebook.interrupt("run-1")


class TestCellResults:
    @pytest.mark.parametrize("same_run", [False, True])
    def test_only_the_newest_cell_execution_remains_visible(
        self,
        notebook: Notebook,
        backend: ScriptedBackend,
        log: list[Event],
        same_run: bool,
    ) -> None:
        running(notebook, backend)
        first = notebook.run("pass", request_id="first")
        old, new = ExecutionId("old"), ExecutionId("new")
        notebook.observe(
            be.Planned(
                first.id, (be.PlannedExecution(old, "cell", "h1", None),)
            )
        )
        notebook.observe(be.Status(old, "running"))
        failed = ErrorOutcome(
            Error(
                kind="exception",
                name="ValueError",
                message="first attempt",
                traceback=None,
                source="marimo",
                severity="error",
                range=None,
                related=[],
            )
        )
        notebook.observe(be.Concluded(old, failed))
        notebook.observe(be.Status(old, "completed"))
        item = Console(
            id=ItemId("o1"),
            execution_id=old,
            seq=0,
            name="stdout",
            text="old output",
        )
        notebook.observe(be.Produced(item))
        if same_run:
            second = first
        else:
            notebook.observe(be.Done(first.id, "failed"))
            second = notebook.run("pass", request_id="second")
        log.clear()
        notebook.observe(
            be.Planned(
                second.id, (be.PlannedExecution(new, "cell", "h2", None),)
            )
        )
        assert names(log) == [
            "console.removed",
            "execution.removed",
            "execution",
        ]
        visible = [
            event.data.execution.id
            for event in notebook._snapshot()
            if isinstance(event.data, ExecutionMessage)
        ]
        assert visible == [new]
        notebook.observe(be.Concluded(new, ValueOutcome(None)))
        notebook.observe(be.Status(new, "completed"))
        if same_run:
            with pytest.raises(ValueError, match="successful run"):
                notebook.observe(be.Done(second.id, "succeeded"))
        notebook.observe(
            be.Done(second.id, "failed" if same_run else "succeeded")
        )
        assert not notebook._retired_executions
        log.clear()
        notebook.observe(be.Produced(item))
        assert not log

    def test_a_new_attempt_cannot_replace_unfinished_work(
        self, notebook: Notebook, backend: ScriptedBackend
    ) -> None:
        running(notebook, backend)
        run = notebook.run("pass", request_id="first")
        notebook.observe(
            be.Planned(
                run.id,
                (be.PlannedExecution(ExecutionId("old"), "cell", "h1", None),),
            )
        )
        with pytest.raises(ValueError, match="unfinished cell execution"):
            notebook.observe(
                be.Planned(
                    run.id,
                    (
                        be.PlannedExecution(
                            ExecutionId("new"), "cell", "h2", None
                        ),
                    ),
                )
            )


class TestAttachments:
    def test_api_clients_attach_and_detach(
        self, notebook: Notebook, log: list[Event]
    ) -> None:
        att = notebook.attach()
        notebook.detach(att.id)
        notebook.detach(att.id)

        assert att.kind == "client"
        assert att.notebook_id == "n1"
        assert names(log) == ["attachment", "attachment.removed"]
