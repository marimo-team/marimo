# Copyright 2026 Marimo. All rights reserved.
"""A cancelled run ends as interrupted without executing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._messaging.notification import (
    CompletedRunNotification,
    ExecutionNotification,
)
from marimo._runtime.commands import CancelRunCommand, ExecuteCellsCommand
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from tests.conftest import MockedKernel


def completed_runs(mocked_kernel: MockedKernel) -> list[tuple[str, str]]:
    return [
        (m.run_id, m.outcome)
        for m in mocked_kernel.stream.parsed_operations
        if isinstance(m, CompletedRunNotification) and m.run_id is not None
    ]


async def test_a_cancelled_run_completes_interrupted_without_executing(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k

    await k.handle_message(CancelRunCommand(run_id="r1"))

    assert completed_runs(mocked_kernel) == [("r1", "interrupted")]
    assert not any(
        isinstance(m, ExecutionNotification)
        for m in mocked_kernel.stream.parsed_operations
    )


async def test_a_later_run_is_unaffected_by_an_earlier_cancellation(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k

    await k.handle_message(CancelRunCommand(run_id="r1"))
    await k.handle_message(
        ExecuteCellsCommand(
            cell_ids=[CellId_t("c")], codes=["x = 1"], run_id="r2"
        )
    )

    assert k.globals["x"] == 1
    assert completed_runs(mocked_kernel) == [
        ("r1", "interrupted"),
        ("r2", "succeeded"),
    ]
