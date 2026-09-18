# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import inspect
from unittest.mock import MagicMock, patch

import pytest

from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._runtime.context.types import _THREAD_LOCAL_CONTEXT
from marimo._runtime.control_flow import MarimoInterrupt
from marimo._runtime.interrupts import InterruptScope


def test_request_raises_only_inside_guard() -> None:
    with InterruptScope() as interrupts:
        with interrupts.guard():
            for _ in range(2):
                with pytest.raises(MarimoInterrupt):
                    interrupts.request()
        # Outside a guard, repeated requests only set the flag.
        interrupts.request()
        interrupts.request()
        assert interrupts.interrupted


def test_guard_records_interrupt_raised_inside() -> None:
    with InterruptScope() as interrupts:
        with pytest.raises(MarimoInterrupt), interrupts.guard():
            raise MarimoInterrupt
        assert interrupts.interrupted


def test_request_between_guards_does_not_raise_in_next_guard() -> None:
    with InterruptScope() as interrupts:
        interrupts.request()
        ran = False
        with interrupts.guard():
            ran = True
        assert ran
        assert interrupts.interrupted


async def test_run_refuses_after_request() -> None:
    interrupts = InterruptScope()
    interrupts.request()

    async def body() -> None:
        pytest.fail("Work started after an interrupt request")

    coro = body()
    with pytest.raises(MarimoInterrupt):
        await interrupts.run(coro)
    assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED


async def test_request_during_task_creation_cancels_work() -> None:
    async def work() -> None:
        pytest.fail("Work started after an interrupt request")

    create_task = asyncio.create_task
    with InterruptScope() as interrupts:

        def create_and_interrupt(coro):
            task = create_task(coro)
            interrupts.request()
            return task

        with patch("asyncio.create_task", side_effect=create_and_interrupt):
            with pytest.raises(MarimoInterrupt):
                await interrupts.run(work())
        assert interrupts.interrupted


async def test_request_cancels_running_work() -> None:
    started = asyncio.Event()

    async def work() -> None:
        started.set()
        await asyncio.sleep(60)

    async def interrupt_once_started() -> None:
        await started.wait()
        interrupts.request()

    with InterruptScope() as interrupts:
        firing = asyncio.create_task(interrupt_once_started())
        with pytest.raises(MarimoInterrupt):
            await interrupts.run(work())
        await firing
        assert interrupts.interrupted


async def test_external_cancellation_propagates_and_cancels_child() -> None:
    started = asyncio.Event()
    child_cancelled = asyncio.Event()

    async def work() -> None:
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            child_cancelled.set()
            raise

    with InterruptScope() as interrupts:
        outer = asyncio.create_task(interrupts.run(work()))
        await started.wait()
        outer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await outer
        await asyncio.wait_for(child_cancelled.wait(), timeout=1)
        assert not interrupts.interrupted


def test_nested_request_marks_both_scopes() -> None:
    ctx = MagicMock(spec=KernelRuntimeContext)
    ctx.interrupt_scope = None
    ctx.stream = MagicMock()
    prior = _THREAD_LOCAL_CONTEXT.runtime_context
    _THREAD_LOCAL_CONTEXT.runtime_context = ctx
    try:
        with InterruptScope() as outer:
            assert ctx.interrupt_scope is outer
            with InterruptScope() as inner:
                assert ctx.interrupt_scope is inner
                inner.request()
                assert inner.interrupted
                assert outer.interrupted
            assert ctx.interrupt_scope is outer
        assert ctx.interrupt_scope is None
    finally:
        _THREAD_LOCAL_CONTEXT.runtime_context = prior


async def test_report_finishes_before_next_operation() -> None:
    ctx = MagicMock()
    ctx.interrupt_scope = None

    with (
        patch("marimo._runtime.interrupts.safe_get_context", return_value=ctx),
        patch("marimo._runtime.interrupts.broadcast_notification") as report,
    ):
        with InterruptScope() as interrupts:
            interrupts.request()
            interrupts.request()
            report.assert_not_called()
        report.assert_called_once()
        with InterruptScope():
            # The old scheduled callback cannot acknowledge a new prompt.
            await asyncio.sleep(0)
            report.assert_called_once()
