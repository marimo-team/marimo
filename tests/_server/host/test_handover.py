# Copyright 2026 Marimo. All rights reserved.
"""Runs take their turn to the kernel in acceptance order."""

from __future__ import annotations

import asyncio

import pytest

from marimo._server.host.handover import Handover, Turn


def test_the_first_run_is_ready_at_once() -> None:
    assert Handover().take().ready


def test_a_run_waits_for_the_one_ahead_to_submit_or_end() -> None:
    handover = Handover()
    first, second = handover.take(), handover.take()
    assert not second.ready
    handover.finish(first)
    assert second.ready


def test_ending_a_middle_run_does_not_release_the_ones_behind_it() -> None:
    handover = Handover()
    first, second, third = (handover.take() for _ in range(3))
    handover.finish(second)
    assert not third.ready
    handover.finish(first)
    assert third.ready


async def test_waiting_runs_resume_in_order() -> None:
    handover = Handover()
    first, second, third = (handover.take() for _ in range(3))
    order: list[str] = []

    async def submit(name: str, turn: Turn) -> None:
        await turn.wait()
        order.append(name)
        handover.finish(turn)

    tasks = [
        asyncio.create_task(submit("third", third)),
        asyncio.create_task(submit("second", second)),
    ]
    await asyncio.sleep(0)
    assert order == []
    handover.finish(first)
    await asyncio.gather(*tasks)
    assert order == ["second", "third"]


def test_finishing_a_turn_again_changes_nothing() -> None:
    handover = Handover()
    first, second, third = (handover.take() for _ in range(3))
    handover.finish(first)
    handover.finish(first)
    assert second.ready
    assert not third.ready


def test_a_submission_with_nothing_ahead_happens_at_once() -> None:
    handover = Handover()
    calls: list[str] = []
    handover.submit(lambda: calls.append("edit"))
    assert calls == ["edit"]
    assert handover.take().ready


async def test_a_submission_waits_its_turn_behind_a_run() -> None:
    handover = Handover()
    run = handover.take()
    calls: list[str] = []
    handover.submit(lambda: calls.append("edit"))
    await asyncio.sleep(0)
    assert calls == []
    handover.finish(run)
    await asyncio.sleep(0)
    assert calls == ["edit"]
    assert handover.take().ready


def test_a_submission_that_fails_still_passes_its_turn() -> None:
    handover = Handover()

    def fail() -> None:
        raise RuntimeError("queue closed")

    with pytest.raises(RuntimeError):
        handover.submit(fail)
    assert handover.take().ready
