# Copyright 2026 Marimo. All rights reserved.
"""The worker's runtime operations through the host."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest

import marimo._pyodide.notebook as worker
from marimo._ast.app_config import _AppConfig
from marimo._config.config import DEFAULT_CONFIG
from marimo._core.code import code_fingerprint
from marimo._messaging.cell_output import CellOutput
from marimo._messaging.input import InputReply
from marimo._messaging.notification import (
    CellNotification,
    CompletedRunNotification,
    ExecutionNotification,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._pyodide import pyodide_session
from marimo._pyodide.pyodide_session import PyodideBridge, PyodideSession
from marimo._runtime.commands import (
    AppMetadata,
    CancelRunCommand,
    CreateNotebookCommand,
    EditCellsCommand,
    ExecuteCellsCommand,
    ExecuteScratchpadCommand,
)
from marimo._runtime.kernel_request_handlers import KernelRequestHandlers
from marimo._session.model import SessionMode
from marimo._session.notebook import AppFileManager
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from pathlib import Path

    from marimo._messaging.notification import NotificationMessage
    from marimo._messaging.types import KernelMessage


@pytest.fixture
def bridge(tmp_path: Path):
    filename = tmp_path / "notebook.py"
    filename.write_text("""import marimo
app = marimo.App()
@app.cell
def _():
    x = 1
    return (x,)
""")
    session = PyodideSession(
        AppFileManager(str(filename)),
        SessionMode.EDIT,
        AppMetadata(
            query_params={},
            cli_args={},
            app_config=_AppConfig(),
            filename=str(filename),
        ),
        DEFAULT_CONFIG,
    )
    bridge = PyodideBridge(session)
    yield bridge
    bridge.close()


async def follow(bridge: PyodideBridge) -> list[dict[str, Any]]:
    """Subscribe and keep collecting the host's events as they arrive."""
    events: list[dict[str, Any]] = []

    def receive(raw: str) -> None:
        event = json.loads(raw)
        if event["event"] != "marimo":
            events.append(event)

    await bridge.notebook.subscribe("reader", None, receive)
    return events


def latest(events: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    return [event["data"][kind] for event in events if event["event"] == kind][
        -1
    ]


def latest_by_id(
    events: list[dict[str, Any]], kind: str
) -> dict[str, dict[str, Any]]:
    """The last state the stream showed for each record of `kind`."""
    return {
        event["data"][kind]["id"]: event["data"][kind]
        for event in events
        if event["event"] == kind
    }


async def call(
    bridge: PyodideBridge,
    operation: str,
    body: dict[str, Any] | None = None,
    *,
    key: str = "run-1",
    **params: str,
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "operation": operation,
        "params": {"notebook_id": bridge.notebook.id, **params},
        "headers": {"idempotency-key": key},
    }
    if body is not None:
        message["body"] = body
    return json.loads(await bridge.notebook.call(json.dumps(message)))


async def settle() -> None:
    """Let the backend's tasks run until they are done or blocked."""
    current = asyncio.current_task()
    for _ in range(50):
        await asyncio.sleep(0)
        if all(t.done() for t in asyncio.all_tasks() if t is not current):
            return


async def started(bridge: PyodideBridge) -> list[dict[str, Any]]:
    """Follow the host and mark the kernel started, as the page does."""
    events = await follow(bridge)
    bridge.session.started.set()
    await settle()
    return events


async def test_worker_input_reply_reaches_its_prompt(bridge: PyodideBridge):
    events = await started(bridge)
    cell_id = latest(events, "cell")["id"]
    accepted = await call(bridge, "runtime.run", {"cells": [{"id": cell_id}]})
    run_id = accepted["body"]["id"]
    await settle()
    deliver(bridge, planned(cell_id, run_id))
    deliver(bridge, running(cell_id, run_id))
    deliver(
        bridge,
        CellNotification(
            cell_id=CellId_t(cell_id),
            run_id=run_id,
            execution_id="e1",
            console=CellOutput.stdin(
                "Password: ", password=True, input_id="prompt"
            ),
        ),
    )
    pending = latest(events, "input")
    assert pending["status"] == "pending"
    response = await call(
        bridge,
        "runtime.input",
        {"value": "secret"},
        input_id="prompt",
        key="answer",
    )
    assert response == {
        "status": 200,
        "body": {**pending, "status": "answered"},
    }
    assert (
        bridge.session._queue_manager.input_queue.get_nowait()
        == InputReply("prompt", "secret")
    )
    assert "secret" not in json.dumps(
        [event for event in events if event["event"] == "input"]
    )


def queued(bridge: PyodideBridge) -> list[Any]:
    queue = bridge.session._queue_manager.control_queue
    commands = []
    while not queue.empty():
        commands.append(queue.get_nowait())
    return commands


def deliver(bridge: PyodideBridge, notification: NotificationMessage) -> None:
    bridge.session._on_message(serialize_kernel_message(notification))


def planned(cell_id: str, run_id: str, execution_id: str = "e1"):
    return ExecutionNotification(
        cell_id=CellId_t(cell_id),
        run_id=run_id,
        execution_id=execution_id,
        phase="planned",
        code="x = 1",
        code_fingerprint=code_fingerprint("x = 1"),
    )


def running(cell_id: str, run_id: str, execution_id: str = "e1"):
    return ExecutionNotification(
        cell_id=CellId_t(cell_id),
        run_id=run_id,
        execution_id=execution_id,
        phase="running",
    )


def finished(cell_id: str, run_id: str, execution_id: str = "e1"):
    return [
        CellNotification(
            cell_id=CellId_t(cell_id),
            run_id=run_id,
            execution_id=execution_id,
            status="running",
        ),
        CellNotification(
            cell_id=CellId_t(cell_id),
            run_id=run_id,
            execution_id=execution_id,
            status="idle",
        ),
        ExecutionNotification(
            cell_id=CellId_t(cell_id),
            run_id=run_id,
            execution_id=execution_id,
            phase="completed",
        ),
        CompletedRunNotification(run_id=run_id, outcome="succeeded"),
    ]


async def test_the_runtime_runs_once_the_page_starts_the_kernel(bridge):
    events = await follow(bridge)
    notebook = latest(events, "notebook")
    assert {"runtime.run", "runtime.interrupt"} <= set(notebook["operations"])
    assert latest(events, "runtime")["status"] == "starting"
    reply = await call(bridge, "runtime.run", {"code": "1"})
    assert reply["status"] == 409

    bridge.session.started.set()
    await settle()
    runtime = latest(events, "runtime")
    assert runtime["status"] == "running"
    assert runtime["marimo_version"]


async def test_running_a_cell_loads_its_imports_and_queues_the_command(
    bridge,
):
    loaded: list[str] = []

    async def load(code: str) -> None:
        loaded.append(code)

    bridge.notebook.set_package_loader(load)
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")

    reply = await call(bridge, "runtime.run", {"cells": [{"id": cell["id"]}]})
    assert reply["status"] == 202
    run_id = reply["body"]["id"]
    assert latest(events, "run")["status"] == "queued"
    await settle()
    [command] = queued(bridge)
    assert isinstance(command, ExecuteCellsCommand)
    assert command.run_id == run_id
    assert command.allow_stdin
    [request] = command.execution_requests
    assert (request.cell_id, request.code, request.code_fingerprint) == (
        cell["id"],
        "x = 1",
        cell["code_fingerprint"],
    )
    assert loaded == ["x = 1"]

    deliver(bridge, planned(cell["id"], run_id))
    for notification in finished(cell["id"], run_id):
        deliver(bridge, notification)
    execution = latest(events, "execution")
    assert execution["cell_id"] == cell["id"]
    assert execution["status"] == "completed"
    assert execution["code_fingerprint"] == cell["code_fingerprint"]
    run = latest(events, "run")
    assert (run["status"], run["outcome"]) == ("completed", "succeeded")


async def test_running_a_cell_loads_the_imports_of_the_whole_document(
    bridge,
):
    loaded: list[str] = []

    async def load(code: str) -> None:
        loaded.append(code)

    bridge.notebook.set_package_loader(load)
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    reply = await call(
        bridge,
        "notebook.edit",
        {
            "changes": [
                {
                    "kind": "put_cell",
                    "base_etag": None,
                    "cell": {"id": "c2", "code": "import json\ny = x"},
                    "after": cell["id"],
                }
            ]
        },
        key="edit-1",
    )
    assert reply["status"] == 200
    queued(bridge)

    reply = await call(bridge, "runtime.run", {"cells": [{"id": cell["id"]}]})
    assert reply["status"] == 202
    await settle()
    [command] = queued(bridge)
    assert isinstance(command, ExecuteCellsCommand)
    assert [r.cell_id for r in command.execution_requests] == [cell["id"]]
    # The dependent cell runs too, so its imports must be loaded as well.
    assert loaded == ["x = 1", "import json\ny = x"]


async def test_scratch_code_runs_against_the_document(bridge):
    bridge.session.instantiated = True
    await started(bridge)
    reply = await call(bridge, "runtime.run", {"code": "x + 1"})
    await settle()
    [command] = queued(bridge)
    assert isinstance(command, ExecuteScratchpadCommand)
    assert command.code == "x + 1"
    assert command.run_id == reply["body"]["id"]
    assert command.allow_stdin
    assert [cell.code for cell in command.notebook_cells] == ["x = 1"]


async def test_runs_reach_the_kernel_in_acceptance_order(bridge):
    gate = asyncio.Event()

    async def load(code: str) -> None:
        if "numpy" in code:
            await gate.wait()

    bridge.notebook.set_package_loader(load)
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    first = await call(bridge, "runtime.run", {"code": "import numpy"})
    second = await call(
        bridge, "runtime.run", {"cells": [{"id": cell["id"]}]}, key="run-2"
    )
    await settle()
    assert queued(bridge) == []

    gate.set()
    await settle()
    assert [command.run_id for command in queued(bridge)] == [
        first["body"]["id"],
        second["body"]["id"],
    ]


async def test_an_edit_waits_behind_a_run_loading_packages(bridge):
    gate = asyncio.Event()

    async def load(code: str) -> None:
        del code
        await gate.wait()

    bridge.notebook.set_package_loader(load)
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    run = await call(bridge, "runtime.run", {"cells": [{"id": cell["id"]}]})
    edit = await call(
        bridge,
        "notebook.edit",
        {
            "changes": [
                {
                    "kind": "put_cell",
                    "base_etag": cell["etag"],
                    "cell": {
                        "id": cell["id"],
                        "code": "x = 2",
                        "name": cell["name"],
                        "config": cell["config"],
                    },
                }
            ]
        },
        key="edit-1",
    )
    assert edit["status"] == 200
    await settle()
    # The edit was accepted after the run, so the kernel sees it after.
    assert queued(bridge) == []

    gate.set()
    await settle()
    execute, update = queued(bridge)
    assert isinstance(execute, ExecuteCellsCommand)
    assert execute.run_id == run["body"]["id"]
    assert isinstance(update, EditCellsCommand)


async def test_each_cell_loads_its_own_imports(bridge):
    loaded: list[str] = []

    async def load(code: str) -> None:
        loaded.append(code)

    bridge.notebook.set_package_loader(load)
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    # A cell mid-edit does not parse; it must not hide another's imports.
    reply = await call(
        bridge,
        "notebook.edit",
        {
            "changes": [
                {
                    "kind": "put_cell",
                    "base_etag": None,
                    "cell": {
                        "id": "c2",
                        "code": "import numpy\ninvalid =",
                        "name": "_",
                        "config": cell["config"],
                    },
                }
            ]
        },
        key="edit-1",
    )
    assert reply["status"] == 200
    await call(bridge, "runtime.run", {"cells": [{"id": cell["id"]}]})
    await settle()
    assert loaded == ["x = 1", "import numpy\ninvalid ="]


async def test_a_failed_package_load_fails_the_run(bridge):
    async def load(code: str) -> None:
        raise RuntimeError(f"no wheel for {code}")

    bridge.notebook.set_package_loader(load)
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    await call(bridge, "runtime.run", {"cells": [{"id": cell["id"]}]})
    await settle()
    assert queued(bridge) == []
    run = latest(events, "run")
    assert (run["status"], run["outcome"]) == ("completed", "failed")


async def test_interrupting_a_queued_run_cancels_it_in_the_kernel(bridge):
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    reply = await call(bridge, "runtime.run", {"cells": [{"id": cell["id"]}]})
    run_id = reply["body"]["id"]
    await settle()
    queued(bridge)

    reply = await call(
        bridge, "runtime.interrupt", key="stop-1", run_id=run_id
    )
    assert reply["status"] == 202
    [command] = queued(bridge)
    assert isinstance(command, CancelRunCommand)
    assert command.run_id == run_id
    deliver(
        bridge, CompletedRunNotification(run_id=run_id, outcome="interrupted")
    )
    run = latest(events, "run")
    assert (run["status"], run["outcome"]) == ("completed", "interrupted")


async def test_an_interrupt_right_after_submission_asks_the_kernel(bridge):
    gate = asyncio.Event()

    async def load(code: str) -> None:
        del code
        await gate.wait()

    bridge.notebook.set_package_loader(load)
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    reply = await call(bridge, "runtime.run", {"cells": [{"id": cell["id"]}]})
    run_id = reply["body"]["id"]
    await settle()
    gate.set()
    # One turn queues the command; the task's done callback has not run yet.
    await asyncio.sleep(0)
    [command] = queued(bridge)
    assert isinstance(command, ExecuteCellsCommand)

    backend = bridge.notebook._backend
    assert backend is not None
    backend.interrupt(run_id)
    [command] = queued(bridge)
    assert isinstance(command, CancelRunCommand)
    assert command.run_id == run_id


class FakeScheduler:
    def __init__(self) -> None:
        self.cancelled = 0

    def cancel_all(self) -> None:
        self.cancelled += 1


async def test_interrupting_a_started_run_halts_the_kernel_queue(
    bridge, monkeypatch: pytest.MonkeyPatch
):
    scheduler = FakeScheduler()
    monkeypatch.setattr(worker, "_active_scheduler", lambda: scheduler)
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    reply = await call(bridge, "runtime.run", {"cells": [{"id": cell["id"]}]})
    run_id = reply["body"]["id"]
    await settle()
    queued(bridge)
    deliver(bridge, planned(cell["id"], run_id))

    reply = await call(
        bridge, "runtime.interrupt", key="stop-1", run_id=run_id
    )
    assert reply["status"] == 202
    assert queued(bridge) == []
    assert scheduler.cancelled == 1

    for notification in finished(cell["id"], run_id):
        deliver(bridge, notification)
    reply = await call(
        bridge, "runtime.interrupt", key="stop-2", run_id=run_id
    )
    assert reply["status"] == 409
    assert scheduler.cancelled == 1


async def test_interrupting_a_run_the_kernel_scheduled(
    bridge, monkeypatch: pytest.MonkeyPatch
):
    scheduler = FakeScheduler()
    monkeypatch.setattr(worker, "_active_scheduler", lambda: scheduler)
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    deliver(bridge, planned(cell["id"], "legacy", "e9"))
    reply = await call(
        bridge, "runtime.interrupt", key="stop-1", run_id="legacy"
    )
    assert reply["status"] == 202
    assert scheduler.cancelled == 1


async def test_interrupting_before_submission_ends_the_run(bridge):
    gate = asyncio.Event()

    async def load(code: str) -> None:
        del code
        await gate.wait()

    bridge.notebook.set_package_loader(load)
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    reply = await call(bridge, "runtime.run", {"cells": [{"id": cell["id"]}]})
    run_id = reply["body"]["id"]
    await settle()
    await call(bridge, "runtime.interrupt", key="stop-1", run_id=run_id)
    await settle()
    gate.set()
    await settle()
    assert queued(bridge) == []
    run = latest(events, "run")
    assert (run["status"], run["outcome"]) == ("completed", "interrupted")


async def test_runs_the_kernel_schedules_appear_on_the_stream(bridge):
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    deliver(bridge, planned(cell["id"], "legacy", "e9"))
    for notification in finished(cell["id"], "legacy", "e9"):
        deliver(bridge, notification)
    runs = [
        event["data"]["run"] for event in events if event["event"] == "run"
    ]
    assert runs[0]["id"] == "legacy"
    assert (runs[-1]["status"], runs[-1]["outcome"]) == (
        "completed",
        "succeeded",
    )
    assert latest(events, "execution")["id"] == "e9"


async def test_a_kernel_exit_fails_the_runtime(bridge):
    events = await started(bridge)
    assert latest(events, "runtime")["status"] == "running"
    bridge.session.exit_reason = "kernel died"
    bridge.session.stopped.set()
    await settle()
    runtime = latest(events, "runtime")
    assert (runtime["status"], runtime["message"]) == ("failed", "kernel died")


async def test_a_failed_launch_fails_the_runtime(
    bridge, monkeypatch: pytest.MonkeyPatch
):
    def refuse(**kwargs: Any) -> None:
        del kwargs
        raise RuntimeError("no kernel")

    monkeypatch.setattr(pyodide_session, "_launch_pyodide_kernel", refuse)
    events = await follow(bridge)
    with pytest.raises(RuntimeError):
        await bridge.session.start()
    await settle()
    runtime = latest(events, "runtime")
    assert (runtime["status"], runtime["message"]) == ("failed", "no kernel")


async def test_the_first_host_run_registers_the_cells(bridge):
    events = await started(bridge)
    cell = latest(events, "cell")
    await call(bridge, "runtime.run", {"cells": [{"id": cell["id"]}]})
    await settle()
    create, execute = queued(bridge)
    assert isinstance(create, CreateNotebookCommand)
    assert create.auto_run is False
    assert isinstance(execute, ExecuteCellsCommand)
    assert bridge.session.instantiated


async def test_a_later_run_proceeds_after_a_failed_load(bridge):
    async def load(code: str) -> None:
        if "numpy" in code:
            raise RuntimeError("no wheel")

    bridge.notebook.set_package_loader(load)
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    first = await call(bridge, "runtime.run", {"code": "import numpy"})
    second = await call(
        bridge, "runtime.run", {"cells": [{"id": cell["id"]}]}, key="run-2"
    )
    await settle()
    runs = latest_by_id(events, "run")
    assert runs[first["body"]["id"]]["outcome"] == "failed"
    assert runs[second["body"]["id"]]["status"] == "queued"
    assert [command.run_id for command in queued(bridge)] == [
        second["body"]["id"]
    ]


async def test_a_later_run_proceeds_after_its_predecessor_is_interrupted(
    bridge,
):
    gate = asyncio.Event()

    async def load(code: str) -> None:
        if "numpy" in code:
            await gate.wait()

    bridge.notebook.set_package_loader(load)
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    first = await call(bridge, "runtime.run", {"code": "import numpy"})
    second = await call(
        bridge, "runtime.run", {"cells": [{"id": cell["id"]}]}, key="run-2"
    )
    await settle()
    reply = await call(
        bridge, "runtime.interrupt", key="stop-1", run_id=first["body"]["id"]
    )
    assert reply["status"] == 202
    await settle()
    runs = latest_by_id(events, "run")
    assert runs[first["body"]["id"]]["outcome"] == "interrupted"
    assert [command.run_id for command in queued(bridge)] == [
        second["body"]["id"]
    ]


async def test_a_kernel_exit_mid_run_fails_the_run(bridge):
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    reply = await call(bridge, "runtime.run", {"cells": [{"id": cell["id"]}]})
    run_id = reply["body"]["id"]
    await settle()
    queued(bridge)
    deliver(bridge, planned(cell["id"], run_id))
    deliver(bridge, running(cell["id"], run_id))

    bridge.session.exit_reason = "boom"
    bridge.session.stopped.set()
    await settle()
    assert latest(events, "runtime")["status"] == "failed"
    run = latest(events, "run")
    assert (run["status"], run["outcome"]) == ("completed", "failed")
    assert latest(events, "execution")["outcome"] == {"kind": "interrupted"}

    # The dying kernel's late completion changes nothing.
    for notification in finished(cell["id"], run_id):
        deliver(bridge, notification)
    assert latest(events, "run")["outcome"] == "failed"
    reply = await call(
        bridge, "runtime.run", {"cells": [{"id": cell["id"]}]}, key="run-2"
    )
    assert reply["status"] == 409


async def test_a_late_cancellation_halts_the_run_once_it_starts(
    bridge, monkeypatch: pytest.MonkeyPatch
):
    scheduler: FakeScheduler | None = None
    monkeypatch.setattr(worker, "_active_scheduler", lambda: scheduler)
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    reply = await call(bridge, "runtime.run", {"cells": [{"id": cell["id"]}]})
    run_id = reply["body"]["id"]
    await settle()
    queued(bridge)

    reply = await call(
        bridge, "runtime.interrupt", key="stop-1", run_id=run_id
    )
    assert reply["status"] == 202
    [command] = queued(bridge)
    assert isinstance(command, CancelRunCommand)

    # The kernel had already taken the run, so the cancel missed it.
    deliver(bridge, planned(cell["id"], run_id))
    scheduler = FakeScheduler()
    deliver(bridge, running(cell["id"], run_id))
    assert scheduler.cancelled == 1
    for notification in finished(cell["id"], run_id):
        deliver(bridge, notification)
    assert scheduler.cancelled == 1


async def test_an_interrupt_waits_for_the_kernel_to_expose_its_scheduler(
    bridge, monkeypatch: pytest.MonkeyPatch
):
    scheduler: FakeScheduler | None = None
    monkeypatch.setattr(worker, "_active_scheduler", lambda: scheduler)
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    reply = await call(bridge, "runtime.run", {"cells": [{"id": cell["id"]}]})
    run_id = reply["body"]["id"]
    await settle()
    queued(bridge)
    deliver(bridge, planned(cell["id"], run_id))

    reply = await call(
        bridge, "runtime.interrupt", key="stop-1", run_id=run_id
    )
    assert reply["status"] == 202
    assert queued(bridge) == []

    scheduler = FakeScheduler()
    deliver(bridge, running(cell["id"], run_id))
    assert scheduler.cancelled == 1


async def test_a_second_subscription_sees_the_run_in_flight(bridge):
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    reply = await call(bridge, "runtime.run", {"cells": [{"id": cell["id"]}]})
    run_id = reply["body"]["id"]
    await settle()
    queued(bridge)
    deliver(bridge, planned(cell["id"], run_id))
    deliver(bridge, running(cell["id"], run_id))

    second: list[dict[str, Any]] = []
    await bridge.notebook.subscribe(
        "second", None, lambda raw: second.append(json.loads(raw))
    )
    kinds = [event["event"] for event in second]
    snapshot = second[: kinds.index("ready")]
    runs = [e["data"]["run"] for e in snapshot if e["event"] == "run"]
    executions = [
        e["data"]["execution"] for e in snapshot if e["event"] == "execution"
    ]
    assert [run["status"] for run in runs] == ["running"]
    assert [execution["status"] for execution in executions] == ["running"]


async def test_cancelling_a_middle_run_keeps_the_order(bridge):
    gate = asyncio.Event()

    async def load(code: str) -> None:
        if "numpy" in code:
            await gate.wait()

    bridge.notebook.set_package_loader(load)
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    first = (await call(bridge, "runtime.run", {"code": "import numpy"}))[
        "body"
    ]["id"]
    second = (await call(bridge, "runtime.run", {"code": "2"}, key="run-2"))[
        "body"
    ]["id"]
    third = (
        await call(
            bridge, "runtime.run", {"cells": [{"id": cell["id"]}]}, key="run-3"
        )
    )["body"]["id"]
    await settle()
    assert queued(bridge) == []

    reply = await call(
        bridge, "runtime.interrupt", key="stop-1", run_id=second
    )
    assert reply["status"] == 202
    await settle()
    # The third still waits for the first, which is loading a package.
    assert queued(bridge) == []
    assert latest_by_id(events, "run")[second]["outcome"] == "interrupted"

    gate.set()
    await settle()
    assert [command.run_id for command in queued(bridge)] == [first, third]


async def test_a_scratch_run_waits_for_the_scratch_run_ahead_to_complete(
    bridge,
):
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    first = (await call(bridge, "runtime.run", {"code": "1"}))["body"]["id"]
    await settle()
    assert [command.run_id for command in queued(bridge)] == [first]

    second = (await call(bridge, "runtime.run", {"code": "2"}, key="run-2"))[
        "body"
    ]["id"]
    # The cell run accepted behind the waiting scratch run waits its turn.
    third = (
        await call(
            bridge, "runtime.run", {"cells": [{"id": cell["id"]}]}, key="run-3"
        )
    )["body"]["id"]
    await settle()
    assert queued(bridge) == []

    deliver(
        bridge, CompletedRunNotification(run_id=first, outcome="succeeded")
    )
    await settle()
    assert [command.run_id for command in queued(bridge)] == [second, third]


async def test_interrupting_a_scratch_run_waiting_for_the_scratchpad(bridge):
    bridge.session.instantiated = True
    events = await started(bridge)
    first = (await call(bridge, "runtime.run", {"code": "1"}))["body"]["id"]
    second = (await call(bridge, "runtime.run", {"code": "2"}, key="run-2"))[
        "body"
    ]["id"]
    third = (await call(bridge, "runtime.run", {"code": "3"}, key="run-3"))[
        "body"
    ]["id"]
    await settle()
    assert [command.run_id for command in queued(bridge)] == [first]

    reply = await call(
        bridge, "runtime.interrupt", key="stop-1", run_id=second
    )
    assert reply["status"] == 202
    await settle()
    assert latest_by_id(events, "run")[second]["outcome"] == "interrupted"
    assert queued(bridge) == []

    deliver(
        bridge, CompletedRunNotification(run_id=first, outcome="succeeded")
    )
    await settle()
    assert [command.run_id for command in queued(bridge)] == [third]


async def test_a_queued_scratch_run_reads_the_document_the_run_ahead_leaves(
    bridge, mocked_kernel, monkeypatch: pytest.MonkeyPatch
):
    bridge.session.instantiated = True
    events = await started(bridge)
    cell = latest(events, "cell")
    kernel = mocked_kernel.k
    kernel._maybe_register_cell(cell["id"], "x = 1", stale=False)
    handlers = KernelRequestHandlers(kernel)
    write = mocked_kernel.stream.write

    def forward(message: KernelMessage) -> None:
        write(message)
        bridge.session._on_message(message)

    monkeypatch.setattr(mocked_kernel.stream, "write", forward)

    first = (
        await call(
            bridge,
            "runtime.run",
            {
                "code": (
                    "import marimo._code_mode as cm\n"
                    "async with cm.get_context() as ctx:\n"
                    "    ctx.cells[0].code\n"
                    '    ctx.edit_cell(ctx.cells[0].id, code="x = 2")\n'
                )
            },
        )
    )["body"]["id"]
    second = (
        await call(
            bridge,
            "runtime.run",
            {
                "code": (
                    "import marimo._code_mode as cm\n"
                    'assert cm.get_context().cells[0].code == "x = 2"\n'
                )
            },
            key="run-2",
        )
    )["body"]["id"]
    await settle()
    [command] = queued(bridge)
    assert command.run_id == first
    await handlers._handle_execute_scratchpad(command)
    await settle()
    assert latest_by_id(events, "run")[first]["outcome"] == "succeeded", (
        latest(events, "execution")
    )
    document = bridge.session.app_manager.app.cell_manager.document
    assert document.cells[0].code == "x = 2"

    [command] = queued(bridge)
    assert command.run_id == second
    await handlers._handle_execute_scratchpad(command)
    runs = latest_by_id(events, "run")
    assert runs[first]["outcome"] == "succeeded"
    assert runs[second]["outcome"] == "succeeded"
