# Copyright 2026 Marimo. All rights reserved.
"""Session backend commands and updates."""

from __future__ import annotations

import asyncio

import pytest

from marimo._code_mode.screenshot_meta import (
    SCREENSHOT_AUTH_TOKEN_KEY,
    SCREENSHOT_FILE_KEY,
    SCREENSHOT_SERVER_URL_KEY,
)
from marimo._core import backend as be, protocol
from marimo._messaging.notification import (
    CellNotification,
    CompletedRunNotification,
    ExecutionNotification,
    StartupProgressNotification,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.host.backend import SessionBackend
from marimo._server.scratchpad import scratchpad_request_metadata
from marimo._session.types import KernelExitInfo, KernelState
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


async def test_a_notebook_without_a_file_cannot_start(
    manager: FakeManager, observed: Observed
) -> None:
    SessionBackend(
        protocol.NotebookId("n1"),
        lambda: None,
        manager,  # type: ignore[arg-type]
        observed,
    ).start(RT1)
    await observed.wait_for(be.Exited)
    assert observed.messages == [
        be.Exited(RT1, "The notebook has no file to run")
    ]
    assert manager.starts == []


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
    b.run(protocol.RunId("run-1"), "while True: pass")
    await asyncio.wait_for(session.submitted.wait(), 5)
    observed.messages.clear()

    b.interrupt(protocol.RunId("run-1"))
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
    concluded = [m for m in observed.messages if isinstance(m, be.Concluded)]
    assert concluded[-1].outcome == (
        protocol.InterruptedOutcome()
        if takes_effect
        else protocol.ValueOutcome(None)
    )
    assert observed.messages[-1] == be.Done(
        protocol.RunId("run-1"), "interrupted" if takes_effect else "succeeded"
    )


async def test_a_session_closing_mid_run_releases_the_run(
    manager: FakeManager, observed: Observed
) -> None:
    b = backend(manager, observed)
    b.start(RT1)
    await observed.wait_for(be.Running)
    session = manager.next_session
    b.run(protocol.RunId("run-1"), "1")
    await asyncio.wait_for(session.submitted.wait(), 5)
    observed.messages.clear()

    session.close()
    await asyncio.wait_for(session.scratchpad_lock.acquire(), 5)
    session.scratchpad_lock.release()

    # `Exited` tells the notebook to end the active run.
    assert observed.kinds() == ["Exited"]
    assert not session.scratchpad_lock.locked()


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
            run_id="browser",
        )
    )
    b.interrupt(protocol.RunId("browser"))
    assert session.interrupts == 1
    session.broadcast(
        CompletedRunNotification(run_id="browser", outcome="interrupted")
    )
    assert observed.messages[-1] == be.Done(
        protocol.RunId("browser"), "interrupted"
    )
    b.interrupt(protocol.RunId("browser"))
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
    assert observed.messages[-1] == be.Status(execution.id, "running")
    assert observed.kinds() == ["Scheduled", "Planned", "Status"]
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
        b.run(protocol.RunId("canceled"), "must_not_execute()")
        if not before_start:
            await asyncio.wait_for(lock.entered.wait(), 5)
        b.interrupt(protocol.RunId("canceled"))
        await observed.wait_for(be.Done)
        assert session.interrupts == 0
        [outcome] = [
            m.outcome for m in observed.messages if isinstance(m, be.Concluded)
        ]
        assert outcome == protocol.InterruptedOutcome()

    observed.messages.clear()
    b.run(protocol.RunId("next"), "42")
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
    b.run(protocol.RunId("failed"), "42")
    await observed.wait_for(be.Done)
    [outcome] = [
        m.outcome for m in observed.messages if isinstance(m, be.Concluded)
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


async def test_host_run_carries_screenshot_metadata(
    manager: FakeManager, observed: Observed
) -> None:
    b = SessionBackend(
        protocol.NotebookId("n1"),
        lambda: "/ws/forecasts.py",
        manager,  # type: ignore[arg-type]
        observed,
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
    b.run(run_id, "ctx.screenshot()")
    await manager.next_session.submitted.wait()
    command = manager.next_session.commands[-1]
    assert command.request.meta == {
        SCREENSHOT_SERVER_URL_KEY: "http://127.0.0.1:2718/base",
        SCREENSHOT_AUTH_TOKEN_KEY: "editor-token",
        SCREENSHOT_FILE_KEY: "/ws/forecasts.py",
        "extra": {"enabled": True},
    }
    assert command.request.headers == {}
    manager.next_session.broadcast(CompletedRunNotification(run_id=run_id))
    assert b._run is not None
    assert b._run.task is not None
    await b._run.task
