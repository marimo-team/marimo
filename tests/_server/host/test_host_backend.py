# Copyright 2026 Marimo. All rights reserved.
"""Session backend commands and updates."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from marimo._code_mode.screenshot_meta import (
    SCREENSHOT_AUTH_TOKEN_KEY,
    SCREENSHOT_FILE_KEY,
    SCREENSHOT_SERVER_URL_KEY,
)
from marimo._core import backend as be, protocol
from marimo._core.code import code_fingerprint
from marimo._core.document import Document, DocumentCell
from marimo._core.stream import Stream
from marimo._messaging.notification import (
    CellNotification,
    CompletedRunNotification,
    ExecutionNotification,
    StartupProgressNotification,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._runtime.commands import (
    CancelRunCommand,
    ExecuteCellsCommand,
    HTTPRequest,
)
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.host.backend import SessionBackend
from marimo._server.scratchpad import scratchpad_request_metadata
from marimo._session.types import KernelExitInfo, KernelState
from marimo._types.encodable import Encodable
from marimo._types.ids import CellId_t
from marimo._version import __version__
from tests._server.host.conftest import (
    FakeManager,
    FakeSession,
    Observed,
)

RT1 = protocol.RuntimeId("rt1")


def backend(manager: FakeManager, observed: Observed) -> SessionBackend:
    return SessionBackend(
        protocol.NotebookId("n1"),
        lambda: "/ws/forecasts.py",
        manager,  # type: ignore[arg-type]
        observed,
        Stream(),
    )


async def test_start_joins_the_session_as_a_secondary_consumer(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    manager.release.clear()

    b.start(RT1)
    await manager.started.wait()
    progress = StartupProgressNotification(
        phase="starting-kernel", logs="", log_mode="append"
    )
    b.notify(serialize_kernel_message(progress))
    manager.release.set()
    await observed.wait_for(be.Running)

    assert manager.starts == [
        {
            "file_key": "/ws/forecasts.py",
            "auto_instantiate": False,
            "main": False,
        }
    ]
    assert observed.messages == [
        be.Starting(RT1, "Starting the kernel"),
        be.Running(RT1, __version__),
    ]


async def test_a_failed_start_reports_the_reason(
    manager: FakeManager, observed: Observed
) -> None:
    manager.next_session = RuntimeError("no such environment")
    backend(manager, observed).start(RT1)
    await observed.wait_for(be.Exited)
    assert observed.messages == [be.Exited(RT1, "no such environment")]

    observed.messages.clear()
    manager.next_session = KeyError()
    backend(manager, observed).start(RT1)
    await observed.wait_for(be.Exited)
    assert observed.messages == [be.Exited(RT1, "KeyError")]


async def test_stop_closes_the_session_and_reports_the_exit(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    b.start(RT1)
    await observed.wait_for(be.Running)
    observed.messages.clear()

    b.stop(RT1)

    assert manager.sessions == {}
    assert manager.next_session.closed
    assert observed.messages == [be.Exited(RT1, None)]


async def test_commands_for_another_runtime_are_ignored(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    b.start(RT1)
    await observed.wait_for(be.Running)
    observed.messages.clear()

    b.stop(protocol.RuntimeId("rt2"))

    assert not manager.next_session.closed
    assert observed.messages == []


async def test_stop_before_the_session_exists_is_carried_out_after(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    manager.release.clear()
    b.start(RT1)
    await manager.started.wait()
    b.stop(RT1)
    manager.release.set()
    await observed.wait_for(be.Exited)
    assert observed.kinds() == ["Running", "Exited"]
    assert manager.next_session.closed


async def test_a_kernel_that_dies_reports_why(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    b.start(RT1)
    await observed.wait_for(be.Running)
    observed.messages.clear()
    session = manager.next_session
    session.state = KernelState.STOPPED
    session.exit_info = KernelExitInfo(
        exitcode=-9, cause="oom", message="Out of memory"
    )

    session.close()  # what the heartbeat does

    assert observed.messages == [be.Exited(RT1, "Out of memory")]


async def test_adopting_a_session_reports_it_running(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    session = FakeSession()
    b.adopt(RT1, session)  # type: ignore[arg-type]
    b.adopt(RT1, session)  # type: ignore[arg-type]
    assert observed.kinds() == ["Running"]
    assert len(session.consumers) == 1


@pytest.mark.parametrize("takes_effect", [False, True])
async def test_interrupt_waits_for_the_kernel_result(
    manager: FakeManager,
    observed: Observed,
    takes_effect: bool,
) -> None:
    b = backend(manager, observed)
    b.start(RT1)
    await observed.wait_for(be.Running)
    session = manager.next_session
    b.run(protocol.RunId("run-1"), "while True: pass", request=None)
    await asyncio.wait_for(session.submitted.wait(), 5)
    # The kernel has started the run, so the backend interrupts it rather
    # than cancelling a queued command.
    session.broadcast(
        ExecutionNotification(
            cell_id=SCRATCH_CELL_ID,
            phase="planned",
            execution_id="attempt",
            code="while True: pass",
            code_fingerprint=code_fingerprint("while True: pass"),
            run_id="run-1",
        )
    )
    observed.messages.clear()

    b.cancel(protocol.RunId("run-1"))
    session.broadcast(
        CellNotification(
            cell_id=SCRATCH_CELL_ID, status="running", run_id="run-1"
        )
    )
    session.broadcast(
        CompletedRunNotification(
            run_id="run-1",
            outcome="interrupted" if takes_effect else "succeeded",
        )
    )
    await observed.wait_for(be.Done)

    assert session.interrupts == 1
    concluded = [m for m in observed.messages if isinstance(m, be.Completed)]
    assert concluded[-1].outcome == (
        protocol.InterruptedOutcome()
        if takes_effect
        else protocol.ValueOutcome(None)
    )
    assert observed.messages[-1] == be.Done(
        protocol.RunId("run-1"), "interrupted" if takes_effect else "succeeded"
    )


async def test_a_session_closing_mid_run_releases_every_run(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    b.start(RT1)
    await observed.wait_for(be.Running)
    session = manager.next_session
    b.run(protocol.RunId("run-1"), "1", request=None)
    b.run(protocol.RunId("run-2"), "2", request=None)
    await asyncio.wait_for(session.submitted.wait(), 5)
    tasks = [run.task for run in b._runs.values()]
    observed.messages.clear()

    session.close()
    await asyncio.wait_for(session.scratchpad_lock.acquire(), 5)
    session.scratchpad_lock.release()
    await asyncio.gather(*(t for t in tasks if t), return_exceptions=True)
    await asyncio.sleep(0)

    # `Exited` tells the notebook to end the unfinished runs.
    assert observed.kinds() == ["Exited"]
    assert not session.scratchpad_lock.locked()
    assert len(tasks) == 2
    assert all(t and t.cancelled() for t in tasks)
    assert b._runs == {}


async def test_interrupting_a_run_started_by_another_client(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    session = manager.next_session
    b.adopt(RT1, session)
    session.broadcast(
        ExecutionNotification(
            cell_id=SCRATCH_CELL_ID,
            phase="planned",
            execution_id="attempt",
            code="while True: pass",
            code_fingerprint=code_fingerprint("while True: pass"),
            run_id="browser",
        )
    )
    b.cancel(protocol.RunId("browser"))
    assert session.interrupts == 1
    session.broadcast(
        CompletedRunNotification(run_id="browser", outcome="interrupted")
    )
    assert observed.messages[-1] == be.Done(
        protocol.RunId("browser"), "interrupted"
    )
    b.cancel(protocol.RunId("browser"))
    assert session.interrupts == 1


async def test_external_scratch_is_adopted_before_compilation(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    session = manager.next_session
    b.adopt(RT1, session)
    observed.messages.clear()
    session.broadcast(
        ExecutionNotification(
            cell_id=SCRATCH_CELL_ID,
            phase="planned",
            code="3 * 3",
            code_fingerprint=code_fingerprint("3 * 3"),
            execution_id="attempt",
            run_id="browser",
        )
    )
    assert observed.kinds() == ["Scheduled", "Planned"]
    planned = observed.messages[-1]
    assert isinstance(planned, be.Planned)
    execution = planned.executions[0]
    assert execution.code == "3 * 3"

    session.broadcast(
        ExecutionNotification(
            cell_id=SCRATCH_CELL_ID,
            phase="running",
            execution_id="attempt",
            run_id="browser",
        )
    )
    assert observed.messages[-1] == be.Started(execution.id)
    assert observed.kinds() == ["Scheduled", "Planned", "Started"]
    session.broadcast(CompletedRunNotification(run_id="browser"))
    assert observed.messages[-1] == be.Done(
        protocol.RunId("browser"), "succeeded"
    )


@pytest.mark.parametrize("before_start", [False, True])
async def test_canceling_a_queued_run_preserves_other_execution(
    manager: FakeManager, observed: Observed, before_start: bool
) -> None:
    class Lock(asyncio.Lock):
        def __init__(self) -> None:
            super().__init__()
            self.entered = asyncio.Event()

        async def acquire(self) -> bool:
            self.entered.set()
            return await super().acquire()

    b = backend(manager, observed)
    session = manager.next_session
    session.scratchpad_lock = lock = Lock()
    b.adopt(RT1, session)
    observed.messages.clear()
    async with lock:
        lock.entered.clear()
        b.run(protocol.RunId("canceled"), "must_not_execute()", request=None)
        if not before_start:
            await asyncio.wait_for(lock.entered.wait(), 5)
        b.cancel(protocol.RunId("canceled"))
        await observed.wait_for(be.Done)
        assert session.interrupts == 0
        [outcome] = [
            m.outcome for m in observed.messages if isinstance(m, be.Completed)
        ]
        assert outcome == protocol.InterruptedOutcome()

    observed.messages.clear()
    b.run(protocol.RunId("next"), "42", request=None)
    await asyncio.wait_for(session.submitted.wait(), 5)
    assert [(c.run_id, c.code) for c in session.commands] == [("next", "42")]
    session.broadcast(CompletedRunNotification(run_id="next"))
    await observed.wait_for(be.Done)


async def test_submission_failure_is_an_error(
    manager: FakeManager, observed: Observed, monkeypatch: pytest.MonkeyPatch
) -> None:
    b = backend(manager, observed)
    session = manager.next_session
    b.adopt(RT1, session)

    def failed(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Kernel channel closed")

    monkeypatch.setattr(session, "put_control_request", failed)
    b.run(protocol.RunId("failed"), "42", request=None)
    await observed.wait_for(be.Done)
    [outcome] = [
        m.outcome for m in observed.messages if isinstance(m, be.Completed)
    ]
    assert outcome == protocol.ErrorOutcome(
        protocol.Error(
            kind="internal",
            name=None,
            message="Kernel channel closed",
            traceback=None,
            source="marimo",
            severity="error",
            range=None,
            related=(),
        )
    )


@pytest.mark.parametrize("cell_run", [False, True])
async def test_only_scratch_runs_carry_screenshot_metadata(
    manager: FakeManager, observed: Observed, cell_run: bool
) -> None:
    b = SessionBackend(
        protocol.NotebookId("n1"),
        lambda: "/ws/forecasts.py",
        manager,  # type: ignore[arg-type]
        observed,
        Stream(),
        request_metadata=lambda session: {
            **scratchpad_request_metadata(
                session,
                server_url="http://127.0.0.1:2718/base",
                auth_token="editor-token",
            ),
            "extra": {"enabled": True},
        },
    )
    b.adopt(RT1, manager.next_session)
    run_id = protocol.RunId("run-screenshot")
    if cell_run:
        b.run_cells(
            run_id,
            Document([DocumentCell(protocol.CellId("a"), "1")], {}),
            [protocol.CellId("a")],
            request=None,
        )
    else:
        b.run(run_id, "ctx.screenshot()", request=None)
    await asyncio.wait_for(manager.next_session.submitted.wait(), 5)
    command = manager.next_session.commands[-1]
    if cell_run:
        assert command.request is None
    else:
        assert command.request.meta == {
            SCREENSHOT_SERVER_URL_KEY: "http://127.0.0.1:2718/base",
            SCREENSHOT_AUTH_TOKEN_KEY: "editor-token",
            SCREENSHOT_FILE_KEY: "/ws/forecasts.py",
            "extra": {"enabled": True},
        }
        assert command.request.headers == {}
        assert command.request.url["path"] == ""
        assert command.request.base_url["path"] == ""
        assert "HTTPRequest(path=''" in repr(command.request)
    task = b._runs[run_id].task
    assert task is not None
    manager.next_session.broadcast(CompletedRunNotification(run_id=run_id))
    await task


@pytest.mark.parametrize("cell_run", [False, True])
@pytest.mark.parametrize("with_metadata", [False, True])
async def test_host_run_carries_the_submitting_request(
    manager: FakeManager,
    observed: Observed,
    cell_run: bool,
    with_metadata: bool,
) -> None:
    b = SessionBackend(
        protocol.NotebookId("n1"),
        lambda: "/ws/forecasts.py",
        manager,  # type: ignore[arg-type]
        observed,
        Stream(),
        request_metadata=(
            (lambda _: {"screenshot": "server"}) if with_metadata else None
        ),
    )
    b.adopt(RT1, manager.next_session)
    run_id = protocol.RunId("run-request")
    url: dict[str, Encodable] = {
        "path": "/notebooks/n1/runtime/runs",
        "port": 2718,
        "scheme": "http",
        "netloc": "127.0.0.1:2718",
        "query": "debug=1",
        "hostname": "127.0.0.1",
    }
    submitted = HTTPRequest(
        url=url,
        base_url={**url, "path": "/", "query": ""},
        headers={"x-trace": "abc"},
        query_params={"debug": ["1"]},
        path_params={"notebook_id": "n1"},
        cookies={"session": "s"},
        user={"is_authenticated": True, "username": "ann"},
        meta={"from": "request", "screenshot": "client"},
    )
    if cell_run:
        b.run_cells(
            run_id,
            Document([DocumentCell(protocol.CellId("a"), "1")], {}),
            [protocol.CellId("a")],
            request=submitted,
        )
    else:
        b.run(run_id, "mo.app_meta().request", request=submitted)
    await asyncio.wait_for(manager.next_session.submitted.wait(), 5)
    command = manager.next_session.commands[-1]
    expected_meta = {
        "from": "request",
        "screenshot": "server" if with_metadata and not cell_run else "client",
    }
    assert command.request == replace(submitted, meta=expected_meta)
    assert submitted.meta == {"from": "request", "screenshot": "client"}
    if cell_run:
        assert command.request is submitted
    task = b._runs[run_id].task
    assert task is not None
    manager.next_session.broadcast(CompletedRunNotification(run_id=run_id))
    await task


async def test_running_cells_instantiates_from_the_host_document(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    b.start(RT1)
    await observed.wait_for(be.Running)
    session = manager.next_session
    document = Document(
        [
            DocumentCell(protocol.CellId("a"), "x = 1"),
            DocumentCell(protocol.CellId("b"), "y = x"),
        ],
        {},
    )

    b.run_cells(
        protocol.RunId("run-1"), document, [protocol.CellId("b")], request=None
    )
    await asyncio.wait_for(session.submitted.wait(), 5)

    (instantiation,) = session.instantiations
    assert instantiation.auto_run is False
    (command,) = session.commands
    assert isinstance(command, ExecuteCellsCommand)
    assert [
        (cell.cell_id, cell.code, cell.code_fingerprint)
        for cell in session.execution_requests
    ] == [(cell.id, cell.code, cell.code_fingerprint) for cell in document]
    assert command.execution_requests == [session.execution_requests[1]]
    assert command.run_id == "run-1"

    session.broadcast(
        CompletedRunNotification(run_id="run-1", outcome="succeeded")
    )
    await observed.wait_for(be.Done)
    assert observed.messages[-1] == be.Done(
        protocol.RunId("run-1"), "succeeded"
    )


@pytest.mark.parametrize("method", ["instantiate", "put_control_request"])
async def test_cell_submission_failure_ends_the_run(
    manager: FakeManager,
    observed: Observed,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
) -> None:
    b = backend(manager, observed)
    session = manager.next_session
    b.adopt(RT1, session)
    observed.messages.clear()

    def failed(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Kernel channel closed")

    monkeypatch.setattr(session, method, failed)
    b.run_cells(
        protocol.RunId("failed"),
        Document([DocumentCell(protocol.CellId("a"), "42")], {}),
        [protocol.CellId("a")],
        request=None,
    )

    assert observed.messages == [be.Done(protocol.RunId("failed"), "failed")]
    assert b._runs == {}


async def test_cell_command_failure_ends_the_run(
    manager: FakeManager,
    observed: Observed,
) -> None:
    b = backend(manager, observed)
    session = manager.next_session
    b.adopt(RT1, session)
    observed.messages.clear()
    document = Document([DocumentCell(protocol.CellId("a"), "42")], {})

    b.run_cells(
        protocol.RunId("failed"),
        document,
        [protocol.CellId("missing")],
        request=None,
    )

    assert observed.messages == [be.Done(protocol.RunId("failed"), "failed")]
    assert b._runs == {}
    assert session.commands == []
    assert session.instantiations == []

    observed.messages.clear()
    b.run_cells(
        protocol.RunId("next"), document, [protocol.CellId("a")], request=None
    )
    await asyncio.wait_for(session.submitted.wait(), 5)
    session.broadcast(CompletedRunNotification(run_id="next"))
    await observed.wait_for(be.Done)
    assert observed.messages == [be.Done(protocol.RunId("next"), "succeeded")]
    assert b._runs == {}


async def test_cell_runs_queue_in_the_kernel_in_order(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    session = manager.next_session
    b.adopt(RT1, session)
    observed.messages.clear()
    document = Document(
        [
            DocumentCell(protocol.CellId("a"), "x = 1"),
            DocumentCell(protocol.CellId("b"), "y = 2"),
        ],
        {},
    )

    b.run_cells(
        protocol.RunId("run-1"), document, [protocol.CellId("a")], request=None
    )
    b.run_cells(
        protocol.RunId("run-2"), document, [protocol.CellId("b")], request=None
    )

    assert [
        (c.run_id, [cell.cell_id for cell in c.execution_requests])
        for c in session.commands
    ] == [
        ("run-1", ["a"]),
        ("run-2", ["b"]),
    ]
    tasks = [run.task for run in b._runs.values() if run.task is not None]
    session.broadcast(CompletedRunNotification(run_id="run-1"))
    session.broadcast(
        ExecutionNotification(
            run_id="run-2",
            execution_id="attempt-2",
            cell_id="b",
            phase="planned",
            code="y = 2",
            code_fingerprint=code_fingerprint("y = 2"),
        )
    )
    session.broadcast(
        ExecutionNotification(
            run_id="run-2",
            execution_id="attempt-2",
            cell_id="b",
            phase="running",
        )
    )
    # Notifications can arrive together, before the run tasks get a turn.
    assert observed.messages == [
        be.Done(protocol.RunId("run-1"), "succeeded"),
        be.Planned(
            protocol.RunId("run-2"),
            (
                be.PlannedExecution(
                    protocol.ExecutionId("attempt-2"),
                    "b",
                    code_fingerprint("y = 2"),
                    None,
                ),
            ),
        ),
        be.Started(protocol.ExecutionId("attempt-2")),
    ]
    assert list(b._runs) == ["run-2"]

    observed.messages.clear()
    session.broadcast(CompletedRunNotification(run_id="run-2"))
    expected = [
        be.Completed(
            protocol.ExecutionId("attempt-2"), protocol.ValueOutcome(None)
        ),
        be.Done(protocol.RunId("run-2"), "succeeded"),
    ]
    assert observed.messages == expected
    assert b._runs == {}
    await asyncio.gather(*tasks)
    await asyncio.sleep(0)
    assert observed.messages == expected


async def test_task_cancellation_preserves_a_completed_run(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    session = manager.next_session
    b.adopt(RT1, session)
    observed.messages.clear()
    document = Document([DocumentCell(protocol.CellId("a"), "x = 1")], {})
    run_id = protocol.RunId("run-1")
    b.run_cells(run_id, document, [protocol.CellId("a")], request=None)
    run = b._runs[run_id]
    task = run.task
    assert task is not None
    await asyncio.sleep(0)

    session.broadcast(CompletedRunNotification(run_id=run_id))
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await asyncio.sleep(0)

    assert not run.translator.interrupted
    assert observed.messages == [be.Done(run_id, "succeeded")]
    assert b._runs == {}


async def submitted(session: FakeSession, count: int) -> list[str]:
    """Wait until the session has received `count` commands."""

    async def wait() -> None:
        while len(session.commands) < count:
            session.submitted.clear()
            await session.submitted.wait()

    await asyncio.wait_for(wait(), 5)
    return [c.run_id for c in session.commands]


async def test_runs_reach_the_kernel_in_acceptance_order(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    session = manager.next_session
    b.adopt(RT1, session)
    observed.messages.clear()
    document = Document([DocumentCell(protocol.CellId("a"), "x = 1")], {})

    b.run(protocol.RunId("run-1"), "1", request=None)
    assert await submitted(session, 1) == ["run-1"]
    # The scratchpad is busy, so the next scratch run waits for it, and
    # the cell run accepted after that waits its turn too.
    b.run(protocol.RunId("run-2"), "2", request=None)
    b.run_cells(
        protocol.RunId("run-3"), document, [protocol.CellId("a")], request=None
    )
    await asyncio.sleep(0)
    assert [c.run_id for c in session.commands] == ["run-1"]

    session.broadcast(CompletedRunNotification(run_id="run-1"))
    assert await submitted(session, 3) == ["run-1", "run-2", "run-3"]
    for run_id in ("run-2", "run-3"):
        session.broadcast(CompletedRunNotification(run_id=run_id))
    await asyncio.gather(*(run.task for run in b._runs.values() if run.task))
    await asyncio.sleep(0)
    assert b._runs == {}
    assert [m.run_id for m in observed.messages if isinstance(m, be.Done)] == [
        "run-1",
        "run-2",
        "run-3",
    ]


async def test_a_cell_run_waits_for_a_scratch_run_accepted_just_before(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    session = manager.next_session
    b.adopt(RT1, session)
    document = Document([DocumentCell(protocol.CellId("a"), "x = 1")], {})

    b.run(protocol.RunId("run-1"), "1", request=None)
    b.run_cells(
        protocol.RunId("run-2"), document, [protocol.CellId("a")], request=None
    )

    assert session.commands == []
    assert await submitted(session, 2) == ["run-1", "run-2"]


@pytest.mark.parametrize("accept_after_interrupt", [False, True])
async def test_interrupting_a_waiting_cell_run_preserves_submission_order(
    manager: FakeManager, observed: Observed, accept_after_interrupt: bool
) -> None:
    b = backend(manager, observed)
    session = manager.next_session
    b.adopt(RT1, session)
    observed.messages.clear()
    document = Document([DocumentCell(protocol.CellId("a"), "x = 1")], {})
    b.run(protocol.RunId("run-1"), "1", request=None)
    await submitted(session, 1)
    b.run(protocol.RunId("run-2"), "2", request=None)
    b.run_cells(
        protocol.RunId("run-3"), document, [protocol.CellId("a")], request=None
    )
    if not accept_after_interrupt:
        b.run_cells(
            protocol.RunId("run-4"),
            document,
            [protocol.CellId("a")],
            request=None,
        )

    b.cancel(protocol.RunId("run-3"))
    await observed.wait_for(be.Done)
    if accept_after_interrupt:
        b.run_cells(
            protocol.RunId("run-4"),
            document,
            [protocol.CellId("a")],
            request=None,
        )
    await asyncio.sleep(0)

    assert observed.messages == [
        be.Done(protocol.RunId("run-3"), "interrupted")
    ]
    assert session.interrupts == 0
    assert [c.run_id for c in session.commands] == ["run-1"]
    session.broadcast(CompletedRunNotification(run_id="run-1"))
    assert await submitted(session, 3) == ["run-1", "run-2", "run-4"]
    for run_id in ("run-2", "run-4"):
        session.broadcast(CompletedRunNotification(run_id=run_id))
    await asyncio.gather(*(run.task for run in b._runs.values() if run.task))
    assert b._runs == {}


async def test_interrupting_a_queued_cell_run_cancels_it_in_the_kernel(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    session = manager.next_session
    b.adopt(RT1, session)
    observed.messages.clear()
    document = Document([DocumentCell(protocol.CellId("a"), "x = 1")], {})

    b.run_cells(
        protocol.RunId("run-1"), document, [protocol.CellId("a")], request=None
    )
    b.cancel(protocol.RunId("run-1"))

    assert session.interrupts == 0
    assert session.commands[-1] == CancelRunCommand(run_id="run-1")

    session.broadcast(
        CompletedRunNotification(run_id="run-1", outcome="interrupted")
    )
    await observed.wait_for(be.Done)
    assert observed.messages == [
        be.Done(protocol.RunId("run-1"), "interrupted")
    ]
    assert b._runs == {}


async def test_a_cancelled_run_that_starts_anyway_is_interrupted(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    session = manager.next_session
    b.adopt(RT1, session)
    observed.messages.clear()
    document = Document([DocumentCell(protocol.CellId("a"), "x = 1")], {})
    b.run_cells(
        protocol.RunId("run-1"), document, [protocol.CellId("a")], request=None
    )
    b.cancel(protocol.RunId("run-1"))
    assert session.interrupts == 0

    # The kernel dequeued the run before the cancellation reached it.
    for execution_id in ("e1", "e2"):
        session.broadcast(
            ExecutionNotification(
                cell_id=CellId_t("a"),
                phase="planned",
                execution_id=execution_id,
                code="x = 1",
                code_fingerprint=code_fingerprint("x = 1"),
                run_id="run-1",
            )
        )
    assert session.interrupts == 1

    session.broadcast(
        CompletedRunNotification(run_id="run-1", outcome="interrupted")
    )
    await observed.wait_for(be.Done)
    assert observed.messages[-1] == be.Done(
        protocol.RunId("run-1"), "interrupted"
    )
    assert b._runs == {}


async def test_interrupting_a_started_cell_run_interrupts_the_kernel(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    session = manager.next_session
    b.adopt(RT1, session)
    document = Document([DocumentCell(protocol.CellId("a"), "x = 1")], {})
    b.run_cells(
        protocol.RunId("run-1"), document, [protocol.CellId("a")], request=None
    )
    session.broadcast(
        ExecutionNotification(
            cell_id=CellId_t("a"),
            phase="planned",
            execution_id="e1",
            code="x = 1",
            code_fingerprint=code_fingerprint("x = 1"),
            run_id="run-1",
        )
    )

    b.cancel(protocol.RunId("run-1"))

    assert session.interrupts == 1
    assert not any(isinstance(c, CancelRunCommand) for c in session.commands)


async def test_an_edit_reaches_the_kernel_at_once_when_nothing_is_ahead(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    session = manager.next_session
    b.adopt(RT1, session)
    b.apply(CancelRunCommand(run_id="edit"))
    assert session.commands == [CancelRunCommand(run_id="edit")]


async def test_an_edit_waits_behind_a_run_still_preparing(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    session = manager.next_session
    b.adopt(RT1, session)
    async with session.scratchpad_lock:
        b.run(protocol.RunId("run-1"), "1", request=None)
        await asyncio.sleep(0)
        b.apply(CancelRunCommand(run_id="edit"))
        await asyncio.sleep(0)
        # The edit was accepted after the run, so it follows the run.
        assert session.commands == []
    assert await submitted(session, 2) == ["run-1", "edit"]
    session.broadcast(CompletedRunNotification(run_id="run-1"))
    await observed.wait_for(be.Done)
