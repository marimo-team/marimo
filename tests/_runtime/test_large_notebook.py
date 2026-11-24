# Copyright 2026 Marimo. All rights reserved.
"""Kernel scaling on large generated notebooks.

Work is measured in Python function calls and emitted bytes, not seconds, so
the bounds hold on a loaded machine. Run with `-s` to print the measurements.
"""

from __future__ import annotations

import cProfile
import math
import pstats
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from marimo._ast.app import InternalApp
from marimo._ast.load import load_notebook_ir
from marimo._ast.parse import parse_notebook
from marimo._runtime.commands import (
    CreateNotebookCommand,
    ExecuteCellCommand,
    UpdateUIElementCommand,
)
from scripts.benchmarks.generate_large_notebook import generate
from tests._runtime._helpers.session import mocked_kernel_session

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from marimo._types.ids import CellId_t
    from scripts.benchmarks.generate_large_notebook import Shape
    from tests._runtime._helpers.session import TestKernel

SMALL = 50
LARGE = 4 * SMALL


@dataclass(frozen=True)
class Work:
    calls: int
    messages: int
    message_bytes: int


@dataclass(frozen=True)
class Measurement:
    cells: int
    run_all: Work
    run_leaf: Work
    run_leaf_while_pending: Work


def _codes(shape: Shape, cells: int) -> dict[CellId_t, str]:
    notebook = parse_notebook(generate(cells, shape), filepath="notebook.py")
    assert notebook is not None
    return InternalApp(load_notebook_ir(notebook)).cell_manager.code_map()


async def _work(tk: TestKernel, run: Callable[[], Awaitable[object]]) -> Work:
    sent = len(tk.stream.messages)
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        await run()
    finally:
        profiler.disable()
    messages = tk.stream.messages[sent:]
    return Work(
        calls=pstats.Stats(profiler).total_calls,  # type: ignore[attr-defined]
        messages=len(messages),
        message_bytes=sum(len(message) for message in messages),
    )


def _instantiate(
    codes: dict[CellId_t, str], *, auto_run: bool
) -> CreateNotebookCommand:
    return CreateNotebookCommand(
        execution_requests=tuple(
            ExecuteCellCommand(cell_id=cell_id, code=code)
            for cell_id, code in codes.items()
        ),
        cell_ids=(),
        set_ui_element_value_request=UpdateUIElementCommand(
            object_ids=[], values=[]
        ),
        auto_run=auto_run,
    )


async def _measure(shape: Shape, cells: int) -> Measurement:
    codes = _codes(shape, cells)
    leaf = next(reversed(codes))

    async def run_leaf(tk: TestKernel) -> Work:
        work = await _work(
            tk,
            lambda: tk.kernel.run(
                [ExecuteCellCommand(cell_id=leaf, code=f"{codes[leaf]}\n")]
            ),
        )
        assert tk.kernel.graph.cells[leaf].run_result_status == "success"
        return work

    with mocked_kernel_session() as tk:
        run_all = await _work(
            tk,
            lambda: tk.kernel.instantiate(_instantiate(codes, auto_run=True)),
        )
        assert not tk.kernel.errors
        assert {
            cell.run_result_status for cell in tk.kernel.graph.cells.values()
        } == {"success"}
        idle = {
            notification.cell_id
            for notification in tk.stream.cell_notifications
            if notification.status == "idle"
        }
        assert idle == set(codes)
        run_leaf_after_run_all = await run_leaf(tk)

    # `runtime.auto_instantiate = false`: nothing has run, so every other
    # cell is still pending when the leaf is run.
    with mocked_kernel_session() as tk:
        await tk.kernel.instantiate(_instantiate(codes, auto_run=False))
        run_leaf_while_pending = await run_leaf(tk)

    return Measurement(
        cells=len(codes),
        run_all=run_all,
        run_leaf=run_leaf_after_run_all,
        run_leaf_while_pending=run_leaf_while_pending,
    )


def _exponent(small: int, large: int) -> float:
    """Growth order `k` such that work ~ cells**k between the two sizes."""
    return math.log(large / small) / math.log(LARGE / SMALL)


# Upper bounds on the growth order of interpreter work. Star-shaped notebooks
# (`smoke`, `outputs`) must stay well below quadratic. Two known costs keep
# the bounds loose, and should be tightened once fixed: a dependency chain is
# quadratic (ancestor walks per registered and per run cell), and running one
# cell recompiles every cell that is still pending.
@pytest.mark.parametrize(
    ("shape", "run_all_order", "run_leaf_order", "run_pending_order"),
    [
        ("smoke", 1.5, 1.0, 1.5),
        ("outputs", 1.5, 1.0, 1.5),
        ("chain", 2.0, 2.0, 2.0),
    ],
)
async def test_kernel_work_scales_with_notebook_size(
    shape: Shape,
    run_all_order: float,
    run_leaf_order: float,
    run_pending_order: float,
) -> None:
    # Pay one-time import costs (markdown extensions, formatters) up front.
    await _measure(shape, 8)
    small = await _measure(shape, SMALL)
    large = await _measure(shape, LARGE)

    orders = {
        "run-all calls": _exponent(small.run_all.calls, large.run_all.calls),
        "run-all bytes": _exponent(
            small.run_all.message_bytes, large.run_all.message_bytes
        ),
        "run-leaf calls": _exponent(
            small.run_leaf.calls, large.run_leaf.calls
        ),
        "run-leaf-while-pending calls": _exponent(
            small.run_leaf_while_pending.calls,
            large.run_leaf_while_pending.calls,
        ),
    }
    print(f"\n{shape}: {small}\n{shape}: {large}\n{shape}: {orders}")

    # Notifications are per cell: a fixed number of messages whose size does
    # not depend on how many other cells exist.
    assert large.run_all.messages <= 12 * large.cells
    assert orders["run-all bytes"] < 1.2
    assert orders["run-all calls"] < run_all_order

    # Running one leaf cell notifies about that cell only.
    assert large.run_leaf.messages == small.run_leaf.messages
    assert orders["run-leaf calls"] < run_leaf_order
    assert orders["run-leaf-while-pending calls"] < run_pending_order
