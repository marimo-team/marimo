# Copyright 2026 Marimo. All rights reserved.
"""Runs on their way to the kernel, kept in acceptance order."""

from __future__ import annotations

import asyncio
from collections import deque


class Turn:
    """A run's place in the order runs reach the kernel."""

    def __init__(self, ahead: asyncio.Event | None) -> None:
        self._ahead = ahead
        self.passed = asyncio.Event()
        """Set once this run and every run ahead of it has submitted or ended."""
        self.finished = False
        """The kernel has the run's command, or the run ended without one."""

    @property
    def ready(self) -> bool:
        """Whether every run ahead has submitted or ended."""
        return self._ahead is None or self._ahead.is_set()

    async def wait(self) -> None:
        """Wait until every run ahead has submitted or ended."""
        if self._ahead is not None:
            await self._ahead.wait()


class Handover:
    """Hand runs to the kernel in the order they were accepted.

    A run may take time to prepare before the kernel has its command: a
    scratch run waits for the scratchpad, a worker run loads packages. The
    run behind it takes its turn once every run ahead has submitted or
    ended, so ending a run in the middle does not let the ones behind it
    pass an earlier one.
    """

    def __init__(self) -> None:
        self._turns: deque[Turn] = deque()

    def take(self) -> Turn:
        """A turn behind every run taken so far."""
        turn = Turn(self._turns[-1].passed if self._turns else None)
        self._turns.append(turn)
        return turn

    def finish(self, turn: Turn) -> None:
        """Record that the run submitted or ended, and pass turns in order."""
        turn.finished = True
        while self._turns and self._turns[0].finished:
            self._turns.popleft().passed.set()
