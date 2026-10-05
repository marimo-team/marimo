# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum

from marimo._types.ids import CellId_t
from marimo._utils.signals import SigintHandler

SCRATCH_CELL_ID = CellId_t("__scratch__")


class ScratchpadState(Enum):
    QUEUED = "queued"
    RUNNING = "running"


@dataclass
class _ScratchpadRun:
    state: ScratchpadState = ScratchpadState.QUEUED
    cancelled: bool = False


class ScratchpadExecutions:
    """Coordinate the control loop with out-of-band cancellation.

    Scheduling and cancellation share one queue, so a run is registered
    before cancellation can arrive. Finished IDs need no tombstones.
    """

    def __init__(self) -> None:
        self._runs: dict[str, _ScratchpadRun] = {}
        self._active_run_id: str | None = None
        self._interrupt_run_id: str | None = None
        self._lock = threading.RLock()

    def schedule(self, run_id: str) -> None:
        with self._lock:
            self._runs[run_id] = _ScratchpadRun()

    def start(self, run_id: str | None) -> bool:
        with SigintHandler.defer(), self._lock:
            run = self._runs.get(run_id) if run_id is not None else None
            if run is None:
                # Existing unregistered scratchpad callers keep their flow.
                return True
            if run.cancelled:
                return False
            run.state = ScratchpadState.RUNNING
            self._active_run_id = run_id
            return True

    def finish(self, run_id: str | None) -> None:
        with SigintHandler.defer(), self._lock:
            if run_id is not None:
                self._runs.pop(run_id, None)
            if self._active_run_id == run_id:
                self._active_run_id = None

    def cancel(self, run_id: str) -> ScratchpadState | None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.cancelled:
                return None
            run.cancelled = True
            if run.state is ScratchpadState.RUNNING:
                self._interrupt_run_id = run_id
            return run.state

    def consume_interrupt(self) -> bool | None:
        """Return whether a targeted signal still matches; None is ordinary."""
        with self._lock:
            target = self._interrupt_run_id
            self._interrupt_run_id = None
            if target is None:
                # Ordinary kernel-wide interrupts are unchanged.
                return None
            return target == self._active_run_id
