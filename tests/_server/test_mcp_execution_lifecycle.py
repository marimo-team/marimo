# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio

import anyio
import pytest

from marimo._ai._tools.types import CodeExecutionResult
from marimo._messaging.notification import CompletedRunNotification
from marimo._messaging.serde import serialize_kernel_message
from marimo._runtime.commands import (
    CancelScratchpadCommand,
    CommandMessage,
    ScheduleScratchpadCommand,
)
from marimo._server.scratchpad import run_scratchpad_command
from tests._server.test_scratchpad import _FakeSession


class ExecutionSession(_FakeSession):
    def __init__(self) -> None:
        super().__init__(auto_complete=False)
        self.dispatched = asyncio.Event()
        self.cancelled = asyncio.Event()

    def put_control_request(
        self, req: CommandMessage, from_consumer_id: object = None
    ) -> None:
        del from_consumer_id
        self.control_requests.append(req)
        if isinstance(req, ScheduleScratchpadCommand):
            self.dispatched.set()
            if self._auto_complete:
                self.complete(req.execution.run_id)
        elif isinstance(req, CancelScratchpadCommand):
            self.cancelled.set()

    def complete(self, run_id: str | None = None) -> None:
        if run_id is None:
            command = self.control_requests[0]
            assert isinstance(command, ScheduleScratchpadCommand)
            run_id = command.execution.run_id
        assert self._active_listener is not None
        self._active_listener.on_notification_sent(
            self.as_session(),
            serialize_kernel_message(CompletedRunNotification(run_id=run_id)),
        )


@pytest.mark.parametrize("cancel", [False, True])
async def test_unfinished_execution_keeps_ownership_until_completion(
    cancel: bool,
) -> None:
    session = ExecutionSession()
    first = asyncio.create_task(
        run_scratchpad_command(
            session.as_session(), code="first()", timeout=0.01
        )
    )
    await session.dispatched.wait()
    if cancel:
        first.cancel()
    await session.cancelled.wait()
    assert not first.done()
    assert session.scratchpad_lock.locked()

    second = asyncio.create_task(
        run_scratchpad_command(session.as_session(), code="second()")
    )
    await asyncio.sleep(0)
    assert len(session.control_requests) == 2
    scheduled, cancelled = session.control_requests
    assert isinstance(scheduled, ScheduleScratchpadCommand)
    assert scheduled.execution.run_id is not None
    assert cancelled == CancelScratchpadCommand(
        run_id=scheduled.execution.run_id
    )

    if cancel:
        first.cancel()
        await asyncio.sleep(0)
        assert not first.done()
    session._auto_complete = True
    session.complete()
    if cancel:
        with pytest.raises(asyncio.CancelledError):
            await first
    else:
        assert await first == CodeExecutionResult(
            success=False, errors=["Execution timed out after 0.01s"]
        )
    assert (await second).success
    assert not session.scratchpad_lock.locked()
    assert session._active_listener is None


async def test_cancellation_while_waiting_for_lock_does_not_dispatch() -> None:
    session = ExecutionSession()
    async with session.scratchpad_lock:
        waiting = asyncio.create_task(
            run_scratchpad_command(session.as_session(), code="never()")
        )
        await asyncio.sleep(0)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        assert session.control_requests == []
        assert session._active_listener is None


async def test_shutdown_releases_cancelled_owner() -> None:
    session = ExecutionSession()
    task = asyncio.create_task(
        run_scratchpad_command(session.as_session(), code="work()")
    )
    await session.dispatched.wait()
    task.cancel()
    await session.cancelled.wait()
    assert session._active_listener is not None
    session._active_listener.on_detach()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1)
    assert not session.scratchpad_lock.locked()


async def test_anyio_cancellation_is_shielded_until_completion() -> None:
    session = ExecutionSession()
    scope = anyio.CancelScope()

    async def run() -> None:
        with scope:
            await run_scratchpad_command(session.as_session(), code="work()")

    task = asyncio.create_task(run())
    await session.dispatched.wait()
    scope.cancel()
    await session.cancelled.wait()
    assert session.scratchpad_lock.locked()
    session.complete()
    await asyncio.wait_for(task, timeout=1)
    assert not session.scratchpad_lock.locked()


async def test_normal_completion_preserves_snapshot_and_skips_cancellation() -> (
    None
):
    session = ExecutionSession()
    session._auto_complete = True
    result = await run_scratchpad_command(session.as_session(), code="42")
    assert result == CodeExecutionResult(success=True)
    assert len(session.control_requests) == 1
    command = session.control_requests[0]
    assert isinstance(command, ScheduleScratchpadCommand)
    assert command.execution.notebook_cells == ()
    assert command.execution.cell_outputs is not None
    assert session.instantiate_calls == []
