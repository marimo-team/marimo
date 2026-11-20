# Copyright 2026 Marimo. All rights reserved.
"""What an interrupt does to runs queued behind it."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from marimo._messaging.notification import CompletedRunNotification
from marimo._runtime.commands import ExecuteCellCommand, ExecuteCellsCommand
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from tests.conftest import MockedKernel


def completed_runs(mocked_kernel: MockedKernel) -> list[str]:
    return [
        m.outcome
        for m in mocked_kernel.stream.parsed_operations
        if isinstance(m, CompletedRunNotification)
    ]


def queued_before_interrupt(mocked_kernel: MockedKernel) -> None:
    mocked_kernel.k.last_interrupt_timestamp = time.time() + 1


async def test_a_host_run_queued_before_an_interrupt_still_runs(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k
    queued_before_interrupt(mocked_kernel)

    await k.handle_message(
        ExecuteCellsCommand(
            execution_requests=[
                ExecuteCellCommand(cell_id=CellId_t("c"), code="x = 1")
            ],
            run_id="host-run",
        )
    )

    assert k.globals["x"] == 1
    assert completed_runs(mocked_kernel) == ["succeeded"]


async def test_a_browser_run_queued_before_an_interrupt_is_discarded(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k
    queued_before_interrupt(mocked_kernel)

    await k.handle_message(
        ExecuteCellsCommand(
            execution_requests=[
                ExecuteCellCommand(cell_id=CellId_t("c"), code="x = 1")
            ]
        )
    )

    assert "x" not in k.globals
    assert completed_runs(mocked_kernel) == ["interrupted"]


async def test_interrupt_discards_a_batch_by_its_submission_time(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k
    k.last_interrupt_timestamp = 2
    await k.handle_message(
        ExecuteCellsCommand(
            execution_requests=[
                ExecuteCellCommand(
                    cell_id=CellId_t("a"), code="x = 1", timestamp=1
                ),
                ExecuteCellCommand(
                    cell_id=CellId_t("b"), code="y = 2", timestamp=3
                ),
            ],
            timestamp=1,
        )
    )
    assert "x" not in k.globals
    assert "y" not in k.globals
    assert completed_runs(mocked_kernel) == ["interrupted"]
