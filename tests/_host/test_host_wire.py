# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import msgspec

from marimo._host import wire
from marimo._host.model import (
    Display,
    Executing,
    Execution,
    ExecutionError,
    Failed,
    Finished,
    Running,
    Runtime,
    Starting,
)
from marimo._types.ids import ExecutionId, NotebookId, ProjectId, RuntimeId

NOW = datetime(2026, 10, 1, 9, 14, 2, tzinfo=timezone.utc)
PROJECT = ProjectId("p1")
NOTEBOOK = NotebookId("n1")
RUNTIME = RuntimeId("r1")


def test_runtime_message_is_progress_while_starting_and_reason_when_failed() -> (
    None
):
    starting = Runtime(
        RUNTIME, NOW, sandbox=True, lifecycle=Starting("Preparing environment")
    )
    wired = wire.runtime(NOTEBOOK, starting)
    assert (wired.status, wired.message) == (
        "starting",
        "Preparing environment",
    )

    failed = replace(starting, lifecycle=Failed("segfault"))
    wired = wire.runtime(NOTEBOOK, failed)
    assert (wired.status, wired.message) == ("failed", "segfault")


def test_running_runtime_encodes_like_the_contract_example() -> None:
    expected = {
        "id": "r1",
        "notebook_id": "n1",
        "status": "running",
        "message": None,
        "sandbox": True,
        "generation": 0,
        "marimo_version": "0.25.0",
        "started_at": "2026-10-01T09:14:02Z",
    }
    running = Runtime(
        RUNTIME,
        NOW,
        sandbox=True,
        lifecycle=Running(),
        marimo_version="0.25.0",
    )
    encoded = msgspec.json.encode(wire.runtime(NOTEBOOK, running))
    assert msgspec.json.decode(encoded) == expected


def test_an_execution_in_flight_is_sent_as_interrupted_when_it_goes() -> None:
    running = Execution(
        ExecutionId("e1"),
        "1 / 0",
        lifecycle=Executing(NOW),
        output=Display("text/plain", "partial"),
    )
    later = NOW.replace(second=9)

    wired = wire.execution(NOTEBOOK, running)
    assert (wired.status, wired.started_at, wired.completed_at) == (
        "running",
        NOW,
        None,
    )
    assert wired.output is not None
    assert wired.output.data == "partial"

    final = wire.interrupted(NOTEBOOK, running, later)
    assert (final.status, final.started_at, final.completed_at) == (
        "interrupted",
        NOW,
        later,
    )
    assert final.output is not None
    assert final.output.data == "partial"

    # One the kernel never began has no start time to report.
    queued = Execution(ExecutionId("e2"), "1 + 1")
    final = wire.interrupted(NOTEBOOK, queued, later)
    assert (final.status, final.started_at, final.completed_at) == (
        "interrupted",
        None,
        later,
    )


def test_a_finished_execution_carries_its_errors() -> None:
    error = ExecutionError("exception", "ZeroDivisionError", "x", None)
    finished = Execution(
        ExecutionId("e1"),
        "1 / 0",
        lifecycle=Finished("failed", NOW, NOW, (error,)),
    )
    wired = wire.execution(NOTEBOOK, finished)
    assert wired.status == "failed"
    assert [e.name for e in wired.errors] == ["ZeroDivisionError"]
