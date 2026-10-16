# Copyright 2026 Marimo. All rights reserved.
"""Notebook commands and state updates from backend messages."""

from __future__ import annotations

from copy import deepcopy

import msgspec
import pytest
from dirty_equals import IsDatetime
from inline_snapshot import snapshot
from msgspec import UNSET
from msgspec.structs import replace

from marimo._core import backend as be
from marimo._core.document import CellSource, Document
from marimo._core.errors import Conflict, NoRuntime, NotFound
from marimo._core.executions import CellExecution, Executions
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.protocol import (
    AttachmentMessage,
    CellId,
    Console,
    ConsoleMessage,
    Custom,
    CustomMessage,
    Display,
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
    RuntimeId,
    RuntimeMessage,
    ValueOutcome,
)
from marimo._core.stream import Event, Stream
from tests._core.conftest import (
    Clock,
    ScriptedBackend,
    finish,
    fold,
    host_at,
    names,
    plan,
    project,
    record,
    request_ids,
    retained_execution,
    runtime_id_of,
)


def running(notebook: Notebook, backend: ScriptedBackend) -> Runtime:
    notebook.start(request_id="req-start")
    notebook.observe(
        be.Running(runtime_id_of(notebook), marimo_version="0.25.0")
    )
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
    def test_runtime_cannot_change_without_an_event(
        self, notebook: Notebook, host: Host, backend: ScriptedBackend
    ) -> None:
        runtime, _ = notebook.start()
        with pytest.raises(AttributeError):
            runtime.status = "running"
        with pytest.raises(AttributeError):
            notebook.runtime = replace(runtime, status="running")
        with pytest.raises(Conflict, match="starting"):
            notebook.run("1", request_id="too-early")

        for events in (
            host.events(notebook_id=notebook.id),
            host.events(0, notebook_id=notebook.id),
        ):
            assert [
                event.data.runtime
                for event in events
                if isinstance(event.data, RuntimeMessage)
            ] == [runtime]
        assert backend.calls == [("start", runtime.id)]

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
        notebook.observe(
            be.Starting(runtime_id_of(notebook), "Preparing the environment")
        )
        notebook.observe(
            be.Running(runtime_id_of(notebook), marimo_version="0.25.0")
        )
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
        notebook.observe(
            be.Exited(runtime_id_of(notebook), "No such environment")
        )

        assert notebook.runtime is not None
        assert notebook.runtime.status == "failed"
        assert notebook.runtime.message == "No such environment"
        assert request_ids(log) == ["req-1", "req-1"]


class TestStop:
    def test_stop_cancels_a_pending_restart(
        self, notebook: Notebook, backend: ScriptedBackend, log: list[Event]
    ) -> None:
        runtime = running(notebook, backend)
        notebook.restart(request_id="restart")
        notebook.stop(request_id="stop")
        log.clear()

        notebook.observe(be.Exited(runtime.id))

        assert notebook.runtime is None
        assert backend.calls == [("stop", runtime.id)]
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
        assert backend.calls == [("stop", runtime.id)]

        notebook.observe(be.Exited(runtime_id_of(notebook), "Stopped"))
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
        run = scratch(notebook)
        notebook.observe(be.Produced(console("o1", "e1", "hi\n")))
        log.clear()

        notebook.stop()
        notebook.observe(be.Exited(runtime_id_of(notebook)))

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
            "document",
            "run",
            "execution",
            "console",
            "ready",
        ]

    def test_a_failed_runtime_is_removed_at_once(
        self, notebook: Notebook, backend: ScriptedBackend, log: list[Event]
    ) -> None:
        notebook.start()
        notebook.observe(be.Exited(runtime_id_of(notebook), "boom"))
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
        run = scratch(notebook)
        notebook.observe(be.Produced(console("o1", "e1", "x")))
        notebook.observe(be.Concluded(ExecutionId("e1"), value("")))
        notebook.observe(be.Status(ExecutionId("e1"), "completed"))
        notebook.observe(be.Done(run.id, "succeeded"))
        log.clear()

        notebook.stop(request_id="stop")
        notebook.observe(be.Exited(runtime_id_of(notebook)))

        assert names(log) == [
            "runtime",
            "runtime.removed",
        ]
        assert request_ids(log) == ["stop", "stop"]
        assert names(host.events(notebook_id=notebook.id)) == [
            "notebook",
            "document",
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
        run = scratch(notebook)
        backend.calls.clear()
        log.clear()

        response = notebook.restart(request_id="req-restart")
        assert response.id != before.id
        assert response.status == "starting"
        assert notebook.runtime is not None
        assert notebook.runtime.id == before.id
        assert notebook.runtime.status == "terminating"
        assert backend.calls == [("stop", before.id)]
        notebook.observe(be.Exited(before.id))
        assert notebook.runtime is not None
        assert notebook.runtime.id == response.id
        assert backend.calls == [
            ("stop", before.id),
            ("forget", run.id),
            ("start", notebook.runtime.id),
        ]
        notebook.observe(
            be.Running(runtime_id_of(notebook), marimo_version="0.25.0")
        )

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

    def test_a_late_exit_from_the_old_kernel_leaves_the_replacement(
        self, notebook: Notebook, backend: ScriptedBackend
    ) -> None:
        before = running(notebook, backend)
        replacement = notebook.restart()
        notebook.observe(be.Exited(before.id))

        notebook.observe(be.Exited(before.id))

        assert notebook.runtime is not None
        assert notebook.runtime.id == replacement.id
        assert notebook.runtime.status == "starting"
        assert backend.calls == [
            ("stop", before.id),
            ("start", replacement.id),
        ]


class TestAdoption:
    def test_a_kernel_someone_else_started_is_published(
        self, notebook: Notebook, backend: ScriptedBackend, log: list[Event]
    ) -> None:
        adopted = notebook.adopt(lambda _: None)
        notebook.observe(
            be.Starting(runtime_id_of(notebook), "Starting the kernel")
        )
        notebook.observe(
            be.Running(runtime_id_of(notebook), marimo_version="0.25.0")
        )

        assert adopted.status == "starting"
        assert backend.calls == []
        assert notebook.runtime is not None
        assert notebook.runtime.id == adopted.id
        assert notebook.runtime.status == "running"
        assert names(log) == ["runtime", "runtime", "runtime"]
        assert request_ids(log) == [UNSET, UNSET, UNSET]

    def test_reports_about_other_kernels_change_nothing(
        self, notebook: Notebook, backend: ScriptedBackend, log: list[Event]
    ) -> None:
        stranger = RuntimeId("rt-stranger")
        notebook.observe(be.Running(stranger, marimo_version="0.25.0"))
        assert notebook.runtime is None

        runtime = running(notebook, backend)
        log.clear()
        notebook.observe(be.Starting(stranger, "Starting the kernel"))
        notebook.observe(be.Exited(stranger, "gone"))

        assert notebook.runtime == runtime
        assert log == []

    def test_only_a_failed_runtime_can_be_replaced(
        self, notebook: Notebook
    ) -> None:
        notebook.start()
        with pytest.raises(Conflict, match="starting"):
            notebook.adopt(lambda _: None)
        notebook.observe(be.Running(runtime_id_of(notebook)))
        with pytest.raises(Conflict, match="running"):
            notebook.adopt(lambda _: None)

    def test_external_relaunch_recovers_a_failed_runtime(
        self, notebook: Notebook, backend: ScriptedBackend, host: Host
    ) -> None:
        before = running(notebook, backend)
        scratch(notebook)
        notebook.observe(be.Exited(runtime_id_of(notebook), "Kernel exited"))
        backend.calls.clear()

        notebook.adopt(lambda _: None)
        notebook.observe(be.Running(runtime_id_of(notebook), "0.26.0"))

        assert notebook.runtime is not None
        assert notebook.runtime.id != before.id
        assert notebook.runtime.marimo_version == "0.26.0"
        assert names(host.events(notebook_id=notebook.id)) == [
            "notebook",
            "document",
            "runtime",
            "run",
            "execution",
            "ready",
        ]
        assert backend.calls == []
        run = notebook.run("1", request_id="after-relaunch")
        assert backend.calls == [("run", run.id, "1")]

    def test_a_kernel_that_dies_on_its_own_fails_and_keeps_results(
        self,
        host: Host,
        notebook: Notebook,
        backend: ScriptedBackend,
        log: list[Event],
    ) -> None:
        running(notebook, backend)
        run = scratch(notebook)
        log.clear()

        notebook.observe(be.Exited(runtime_id_of(notebook), "killed"))

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
        # Completed scratch outputs live in the host history; late reports
        # cannot recreate notebook state.
        notebook.observe(be.Produced(console("late", "e1", "background")))
        assert live == []
        assert names(
            host.events(cursor, notebook_id=notebook.id, run_id=run.id)
        ) == ["ready"]
        assert names(host.events(notebook_id=notebook.id, run_id=run.id)) == [
            "run",
            "execution",
            "ready",
        ]
        host.remove_notebook(notebook.id)
        assert names(live) == ["execution.removed", "run.removed"]
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
        assert backend.calls == [("run", run.id, "3 * 3"), ("forget", run.id)]
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
                    id=run.id,
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
                    inputs={},
                    id=ExecutionId("e7"),
                    outcome=ValueOutcome(
                        display=DisplayData(
                            data="working<pre>9</pre>", mimetype="text/html"
                        )
                    ),
                    run_id=run.id,
                    runtime_id=notebook.runtime.id,
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

    def test_request_keys_do_not_identify_runs(
        self, notebook: Notebook, backend: ScriptedBackend
    ) -> None:
        running(notebook, backend)
        first = notebook.run("1", request_id="same")
        with pytest.raises(Conflict, match=first.id):
            notebook.run("1", request_id="same")
        notebook.observe(be.Done(first.id, "succeeded"))
        second = notebook.run("2", request_id="same")
        assert second.id != first.id
        # A completed run with no executions is released at once.
        assert backend.calls == [
            ("run", first.id, "1"),
            ("forget", first.id),
            ("run", second.id, "2"),
        ]

    def test_one_run_at_a_time(
        self, notebook: Notebook, backend: ScriptedBackend, log: list[Event]
    ) -> None:
        running(notebook, backend)
        first = notebook.run("1", request_id="first")
        with pytest.raises(Conflict, match=first.id):
            notebook.run("2", request_id="second")
        notebook.observe(be.Done(first.id, "succeeded"))
        final = next(
            event.data
            for event in reversed(log)
            if isinstance(event.data, RunMessage)
        )
        assert isinstance(final, RunMessage)
        assert final.run.status == "completed"
        assert final.run.started_at is None
        assert final.run.completed_at is not None
        assert notebook.run("2", request_id="second").status == "queued"

    def test_an_item_replaces_itself_by_id(
        self, host: Host, notebook: Notebook, backend: ScriptedBackend
    ) -> None:
        running(notebook, backend)
        run = scratch(notebook)
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
        final = next(
            event.data
            for event in reversed(log)
            if isinstance(event.data, RunMessage)
        )
        assert isinstance(final, RunMessage)
        assert final.run.caused_by == "e1"
        assert notebook.executions.run(original.id) is None

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
        final = next(
            event.data
            for event in reversed(log)
            if isinstance(event.data, RunMessage)
        )
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
                        related=(),
                    )
                ),
            )
        )
        notebook.observe(be.Status(ExecutionId("child"), "completed"))
        # Even an empty execution queue is not an authoritative end to scheduling.
        current = notebook.executions.run(run.id)
        assert current is not None
        assert current.status == "running"
        assert current.outcome is None
        with pytest.raises(ValueError, match="successful"):
            notebook.observe(be.Done(run.id, "succeeded"))
        notebook.observe(be.Done(run.id, outcome))
        final = next(
            event.data
            for event in reversed(log)
            if isinstance(event.data, RunMessage)
        )
        assert isinstance(final, RunMessage)
        assert final.run.outcome == outcome
        assert final.run.status == "completed"
        log.clear()
        # Released scratch records cannot reopen or acquire more output.
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
        assert log == []


class TestInterrupt:
    def test_asks_the_backend_while_in_progress(
        self, notebook: Notebook, backend: ScriptedBackend
    ) -> None:
        running(notebook, backend)
        run = scratch(notebook)
        backend.calls.clear()

        notebook.interrupt(run.id)

        assert backend.calls == [("interrupt", run.id)]

    def test_refuses_unknown_and_finished_runs(
        self, notebook: Notebook, backend: ScriptedBackend
    ) -> None:
        running(notebook, backend)
        with pytest.raises(NotFound):
            notebook.interrupt("nope")
        run = scratch(notebook)
        notebook.observe(be.Concluded(ExecutionId("e1"), value("9")))
        notebook.observe(be.Status(ExecutionId("e1"), "completed"))
        notebook.observe(be.Done(run.id, "succeeded"))
        with pytest.raises(NotFound):
            notebook.interrupt(run.id)


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
                related=(),
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
            *([] if same_run else ["run.removed"]),
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
        assert not any(r.retired for r in notebook.executions._runs.values())
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

    def test_one_identity_attaches_separately(
        self, notebook: Notebook, log: list[Event]
    ) -> None:
        first = notebook.attach(identity="k1", kind="agent", name="Codex")
        second = notebook.attach(identity="k1", kind="agent", name="Codex")

        assert first.id != second.id
        assert first.identity == second.identity == "k1"
        assert names(log) == ["attachment", "attachment"]
        assert _attachment_ids(notebook) == {first.id, second.id}

    def test_detach_leaves_other_attachments_with_the_identity(
        self, notebook: Notebook, log: list[Event]
    ) -> None:
        first = notebook.attach(identity="k1")
        second = notebook.attach(identity="k1")
        log.clear()

        notebook.detach(first.id)

        assert names(log) == ["attachment.removed"]
        assert _attachment_ids(notebook) == {second.id}

    def test_attach_without_an_identity_omits_it_on_the_wire(
        self, notebook: Notebook, log: list[Event]
    ) -> None:
        att = notebook.attach()

        assert att.identity is UNSET
        wire = msgspec.json.decode(msgspec.json.encode(log[0].data))
        assert "identity" not in wire["attachment"]


class TestEmit:
    def test_emit_publishes_a_custom_event_on_the_notebook_stream(
        self, notebook: Notebook, log: list[Event]
    ) -> None:
        custom = notebook.emit("marimo.test", {"hello": 1}, request_id="req-1")

        assert custom == Custom(type="marimo.test", data={"hello": 1})
        assert names(log) == ["custom"]
        assert log[0].notebook_id == notebook.id
        published = log[0].data
        assert isinstance(published, CustomMessage)
        assert published.custom == custom
        assert published.request_id == "req-1"
        assert published.time is not UNSET

    def test_emit_rejects_data_that_is_not_json(
        self, notebook: Notebook, log: list[Event]
    ) -> None:
        with pytest.raises(TypeError):
            notebook.emit("marimo.test", object())
        assert "custom" not in names(log)

    def test_emit_rejects_an_empty_type(
        self, notebook: Notebook, log: list[Event]
    ) -> None:
        with pytest.raises(ValueError):
            notebook.emit("", 1)
        assert "custom" not in names(log)

    def test_emit_on_a_closed_notebook_raises(
        self, host: Host, notebook: Notebook
    ) -> None:
        host.remove_notebook(notebook.id)
        with pytest.raises(NotFound):
            notebook.emit("marimo.test", {"hello": 1})


def _attachment_ids(notebook: Notebook) -> set[str]:
    return {
        event.data.attachment.id
        for event in notebook._snapshot()
        if isinstance(event.data, AttachmentMessage)
    }


@pytest.mark.parametrize("cleanup", ["expire", "replace", "clear"])
async def test_outputs_follow_their_execution_through_updates_and_removal(
    cleanup: str,
) -> None:
    clock = Clock()
    host, notebook = await host_at(clock)
    run = notebook.run("code", request_id="request")
    first = plan(notebook, run, "first", "a" if cleanup != "expire" else None)
    second = plan(
        notebook, run, "second", "b" if cleanup != "expire" else None
    )
    first_console = Console(first, ItemId("first-console"), "stdout", 0, "a")
    first_display = Display(
        execution_id=first,
        id=ItemId("first-display"),
        seq=1,
        mimetype="text/plain",
        data="b",
    )
    second_console = Console(
        second, ItemId("second-console"), "stdout", 0, "c"
    )
    second_display = Display(
        execution_id=second,
        id=ItemId("second-display"),
        seq=1,
        mimetype="text/plain",
        data="d",
    )
    for item in (second_console, first_console, second_display, first_display):
        notebook.observe(be.Produced(item))
    first_console = replace(first_console, text="updated")
    notebook.observe(be.Produced(first_console))
    finish(notebook, first)
    finish(notebook, second)
    notebook.observe(be.Done(run.id, "succeeded"))
    initial = host.events(notebook_id=notebook.id)
    assert [
        getattr(event.data, event.kind)
        for event in initial
        if event.kind in {"console", "display"}
    ] == [first_console, first_display, second_console, second_display]

    live: list[Event] = []
    snapshots: list[dict] = []

    def updated(event: Event) -> None:
        live.append(event)
        snapshots.append(fold(notebook._snapshot()))

    host.subscribe(
        updated,
        notebook_id=notebook.id,
        types={"run", "execution", "console", "display"},
    )
    if cleanup == "expire":
        clock.now = 10
        host.expire()
    elif cleanup == "replace":
        replacement = notebook.run("code", request_id="replacement")
        plan(notebook, replacement, "new", "a")
    else:
        host.remove_notebook(notebook.id)

    assert [
        (event.name, event.data.id)
        for event in live
        if event.name.endswith(".removed")
    ] == [
        ("console.removed", first_console.id),
        ("display.removed", first_display.id),
        ("execution.removed", first),
        *(
            []
            if cleanup == "replace"
            else [
                ("console.removed", second_console.id),
                ("display.removed", second_display.id),
                ("execution.removed", second),
                ("run.removed", run.id),
            ]
        ),
    ]
    assert fold(live, fold(initial)) == fold(notebook._snapshot())
    # A transition updates state before notifying observers.
    assert all(
        ("execution", first) not in state
        for event, state in zip(live, snapshots, strict=True)
        if event.name.endswith(".removed")
    )


@pytest.mark.parametrize("run_id", [None, "previous-run"])
async def test_initial_results_are_published_and_replaced_by_live_execution(
    run_id: str | None,
) -> None:
    retained = retained_execution(run_id=run_id)
    document = Document(record().id, [CellSource(CellId("c1"), "42")], {})
    host = Host(operations=[])
    host.update_project(project())
    host.add_notebook(
        record(),
        lambda _, sink: Notebook(
            document,
            Executions.restore({CellId("c1"): retained}, cells=document),
            ScriptedBackend(),
            sink,
        ),
    )
    live: list[Event] = []
    host.subscribe(live.append, notebook_id=record().id)
    notebook = await host.notebook(record().id)
    assert notebook.runtime is None
    expected = {
        ("execution", retained.execution.id): retained.execution,
        ("console", retained.outputs[0].id): retained.outputs[0],
    }
    assert fold(live) == fold(host.events(notebook_id=notebook.id)) == expected
    assert names(live) == ["cell", "document", "execution", "console"]

    notebook.start()
    notebook.observe(be.Running(runtime_id_of(notebook)))
    run = notebook.run("42", request_id="run")
    execution_id = plan(notebook, run, "new", cell="c1")
    state = fold(host.events(notebook_id=notebook.id))
    assert set(state) == {("run", run.id), ("execution", execution_id)}
    assert fold(live) == state


async def test_current_cell_results_can_seed_another_notebook() -> None:
    _, notebook = await host_at(Clock())
    notebook.replace([CellSource(CellId("c1"), "code")], {})
    run = notebook.run("code", request_id="request")
    execution = plan(notebook, run, "cell", "c1")
    notebook.observe(
        be.Produced(Console(execution, ItemId("out"), "stdout", 0, "x"))
    )
    finish(notebook, execution)
    notebook.observe(be.Done(run.id, "succeeded"))
    document = Document.from_records(
        notebook.document._record, list(notebook.document)
    )
    retained = notebook.executions.current(CellId("c1"))
    assert retained is not None
    restored = Notebook(
        document,
        Executions.restore({CellId("c1"): retained}, cells=document),
        ScriptedBackend(),
        Stream(history=0),
    )
    assert restored.document._record == notebook.document._record
    assert list(restored.document) == list(notebook.document)
    assert restored.executions.current(CellId("c1")) == retained
    assert fold(restored._snapshot()) == {
        key: value
        for key, value in fold(notebook._snapshot()).items()
        if key[0] != "run"
    }


@pytest.mark.parametrize("saved", [False, True])
def test_restoration_preserves_revisions_and_outputs(
    saved: bool,
) -> None:
    document = Document(
        record().id,
        [CellSource(CellId("c2"), "pass"), CellSource(CellId("c1"), "42")],
        {"width": "full"},
        policy="lazy",
        saved=saved,
    )
    # The output belongs to the previous source, and the saved revision can
    # precede the current one. Neither is rewritten during restoration.
    document.replace(
        [CellSource(CellId("c2"), "pass"), CellSource(CellId("c1"), "43")],
        {"width": "full"},
    )
    seed = retained_execution(run_id="historical-run")
    retained = CellExecution(
        seed.execution,
        (
            *seed.outputs,
            Display(
                execution_id=seed.execution.id,
                id=ItemId("display"),
                seq=1,
                mimetype="application/json",
                data='{"values": [1, 2]}',
            ),
            replace(seed.outputs[0], id=ItemId("last"), seq=2),
        ),
    )
    document_record, cells = deepcopy((document._record, list(document)))
    restored = Document.from_records(document_record, cells[::-1])
    backend = ScriptedBackend()
    notebook = Notebook(
        restored,
        Executions.restore({CellId("c1"): retained}, cells=restored),
        backend,
        Stream(history=0),
    )
    assert notebook.document._record == document._record
    assert list(notebook.document) == list(document)
    assert notebook.executions.current(CellId("c1")) == retained
    assert backend.calls == []
    outputs = [
        e for e in notebook._snapshot() if e.kind in ("console", "display")
    ]
    assert [getattr(e.data, e.kind).seq for e in outputs] == [0, 1, 2]
    # Restoration copies the supplied records.
    document_record.app_config["width"] = "medium"
    assert notebook.document._record == document._record


async def test_edits_preserve_results_and_deletion_removes_them() -> None:
    retained = retained_execution()
    document = Document(record().id, [CellSource(CellId("c1"), "42")], {})
    host = Host(operations=[])
    host.update_project(project())
    host.add_notebook(
        record(),
        lambda _, sink: Notebook(
            document,
            Executions.restore({CellId("c1"): retained}, cells=document),
            ScriptedBackend(),
            sink,
        ),
    )
    notebook = await host.notebook(record().id)
    notebook.replace([CellSource(CellId("c1"), "43")], {})
    assert notebook.executions.current(CellId("c1")) == retained
    assert (
        next(iter(notebook.document)).code_hash != retained.execution.code_hash
    )
    live: list[Event] = []
    host.subscribe(live.append, notebook_id=notebook.id)
    notebook.replace([], {})
    assert list(notebook.document) == []
    assert notebook.executions.current(CellId("c1")) is None
    assert fold(host.events(notebook_id=notebook.id)) == {}
    assert names(live) == [
        "console.removed",
        "execution.removed",
        "cell.removed",
        "document",
    ]


async def test_restoration_excludes_live_work_and_cleans_up_deleted_active_cells() -> (
    None
):
    _, notebook = await host_at(Clock())
    notebook.replace([CellSource(CellId("c1"), "code")], {})
    notebook.attach()
    run = notebook.run("code", request_id="request")
    execution = plan(notebook, run, "active", "c1")
    notebook.observe(
        be.Produced(Console(execution, ItemId("out"), "stdout", 0, "x"))
    )
    assert notebook.executions.current(CellId("c1")) is None
    document = Document.from_records(
        notebook.document._record, list(notebook.document)
    )
    executions = Executions.restore(
        {
            cell.id: result
            for cell in notebook.document
            if (result := notebook.executions.current(cell.id)) is not None
        },
        cells=document,
    )
    restored = Notebook(
        document, executions, ScriptedBackend(), Stream(history=0)
    )
    assert names(restored._snapshot()) == ["cell", "document"]
    notebook.replace([], {})
    finish(notebook, execution)
    notebook.observe(be.Done(run.id, "succeeded"))
    assert list(notebook.document) == []
    assert fold(notebook._snapshot()) == {}


async def test_source_edits_keep_live_results_until_the_cell_is_deleted() -> (
    None
):
    host, notebook = await host_at(Clock())
    notebook.replace([CellSource("c1", "42")], {})
    run = notebook.run("42", request_id="run")
    execution = plan(notebook, run, "result", "c1")
    notebook.observe(
        be.Produced(Console(execution, ItemId("out"), "stdout", 0, "hello"))
    )
    finish(notebook, execution)
    notebook.observe(be.Done(run.id, "succeeded"))
    retained = notebook.executions._records()

    notebook.replace([CellSource("c1", "43")], {})
    assert notebook.executions._records() == retained

    live: list[Event] = []
    host.subscribe(live.append, notebook_id=notebook.id)
    notebook.replace([], {})
    assert list(notebook.document) == []
    assert fold(host.events(notebook_id=notebook.id)) == {}
    assert names(live) == [
        "console.removed",
        "execution.removed",
        "run.removed",
        "cell.removed",
        "document",
    ]


async def test_deleting_an_active_cell_releases_its_result_when_the_run_ends() -> (
    None
):
    host, notebook = await host_at(Clock())
    notebook.replace([CellSource("c1", "42")], {})
    run = notebook.run("42", request_id="run")
    execution = plan(notebook, run, "result", "c1")
    notebook.replace([], {})
    notebook.observe(
        be.Produced(Console(execution, ItemId("out"), "stdout", 0, "hello"))
    )
    finish(notebook, execution)
    notebook.observe(be.Done(run.id, "succeeded"))
    assert list(notebook.document) == []
    assert fold(notebook._snapshot()) == {}
    assert fold(host.events(notebook_id=notebook.id)) == {}
