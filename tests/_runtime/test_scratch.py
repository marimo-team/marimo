# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime.scratch import ScratchpadExecutions, ScratchpadState


def test_pending_cancellation_skips_execution() -> None:
    runs = ScratchpadExecutions()
    runs.schedule("queued")
    assert runs.cancel("queued") is ScratchpadState.QUEUED
    assert runs.start("queued") is False
    assert runs.consume_interrupt() is None
    runs.finish("queued")
    assert runs.cancel("queued") is None


def test_active_cancellation_is_targeted_and_idempotent() -> None:
    runs = ScratchpadExecutions()
    runs.schedule("active")
    assert runs.start("active") is True
    assert runs.cancel("active") is ScratchpadState.RUNNING
    assert runs.cancel("active") is None
    assert runs.consume_interrupt() is True
    assert runs.consume_interrupt() is None
    runs.finish("active")
    assert runs.cancel("active") is None


def test_delayed_interrupt_does_not_target_successor() -> None:
    runs = ScratchpadExecutions()
    runs.schedule("first")
    runs.start("first")
    runs.cancel("first")
    runs.finish("first")
    runs.schedule("second")
    runs.start("second")
    assert runs.consume_interrupt() is False
    # An ordinary interrupt still works after the stale one is consumed.
    assert runs.consume_interrupt() is None


def test_unregistered_scratchpad_keeps_existing_flow() -> None:
    runs = ScratchpadExecutions()
    assert runs.start(None) is True
    runs.finish(None)
    assert runs.start("legacy") is True
    runs.finish("legacy")
    assert runs.consume_interrupt() is None
