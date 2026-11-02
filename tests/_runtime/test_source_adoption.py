# Copyright 2026 Marimo. All rights reserved.
"""Which source the kernel runs, and when it takes new source.

The kernel adopts a cell's source only from a run that carries it. Cells
that have never run keep the source they were loaded with until a run
needs them. These tests pin that contract, so the commands that deliver
source can change without changing what runs.
"""

from __future__ import annotations

from marimo._runtime.commands import (
    CreateNotebookCommand,
    DeleteCellCommand,
    ExecuteCellCommand,
    UpdateCellConfigCommand,
    UpdateUIElementCommand,
)
from marimo._runtime.runtime import Kernel
from marimo._types.ids import CellId_t
from tests.conftest import MockedKernel

A, B, C = CellId_t("a"), CellId_t("b"), CellId_t("c")


def run(cell_id: CellId_t, code: str) -> ExecuteCellCommand:
    return ExecuteCellCommand(cell_id=cell_id, code=code)


async def load(k: Kernel, *cells: tuple[CellId_t, str]) -> None:
    """Instantiate without running, so every cell is pending."""
    await k.instantiate(
        CreateNotebookCommand(
            execution_requests=tuple(run(cid, code) for cid, code in cells),
            cell_ids=tuple(cid for cid, _ in cells),
            set_ui_element_value_request=(
                UpdateUIElementCommand.from_ids_and_values([])
            ),
            auto_run=False,
        )
    )


async def test_a_run_adopts_source_for_its_targets_only(k: Kernel) -> None:
    await k.run([run(A, "x = 1"), run(B, "y = x + 1")])
    # A is edited to `x = 10` without a run. Only B's run reaches the kernel.
    await k.run([run(B, "y = x + 100")])
    assert k.graph.cells[A].code == "x = 1"
    assert k.globals["y"] == 101


async def test_a_run_with_changed_source_reruns_children(k: Kernel) -> None:
    await k.run([run(A, "x = 1"), run(B, "y = x + 1")])
    await k.run([run(A, "x = 5")])
    assert k.globals["y"] == 6
    # Running unchanged source runs it again.
    k.globals["y"] = None
    await k.run([run(A, "x = 5")])
    assert k.globals["y"] == 6


async def test_a_run_with_changed_source_marks_children_stale_lazily(
    lazy_kernel: Kernel,
) -> None:
    k = lazy_kernel
    await k.run([run(A, "x = 1"), run(B, "y = x + 1")])
    await k.run([run(A, "x = 5")])
    assert k.graph.cells[B].stale
    assert k.globals["y"] == 2


async def test_a_run_registers_never_run_ancestors_with_pending_source(
    k: Kernel,
) -> None:
    await load(k, (A, "x = 7"), (B, "y = x + 1"), (C, "z = 42"))
    assert not k.graph.cells
    await k.run([run(B, "y = x + 1")])
    assert k.globals["y"] == 8
    assert set(k.graph.cells) == {A, B}
    assert set(k._uninstantiated_execution_requests) == {C}


async def test_a_never_run_ancestor_that_does_not_parse_is_skipped(
    k: Kernel,
) -> None:
    """Known limit. Its names are unknown, so it is not seen as an ancestor."""
    await load(k, (A, "x = ("), (B, "y = x + 1"))
    await k.run([run(B, "y = x + 1")])
    assert k.graph.cells[B].run_result_status == "exception"
    assert A in k._uninstantiated_execution_requests
    assert not k.errors


async def test_deleting_a_cell_reruns_its_children(k: Kernel) -> None:
    await k.run([run(A, "x = 1"), run(B, "y = x + 1")])
    await k.delete_cell(DeleteCellCommand(cell_id=A))
    assert "x" not in k.globals
    assert k.graph.cells[B].run_result_status == "exception"


async def test_deleting_a_cell_marks_its_children_stale_lazily(
    lazy_kernel: Kernel,
) -> None:
    k = lazy_kernel
    await k.run([run(A, "x = 1"), run(B, "y = x + 1")])
    await k.delete_cell(DeleteCellCommand(cell_id=A))
    assert k.graph.cells[B].stale
    assert k.globals["y"] == 2


async def test_enabling_a_stale_cell_runs_its_adopted_source(
    k: Kernel,
) -> None:
    await k.run([run(A, "x = 1"), run(B, "y = x + 1")])
    await k.set_cell_config(
        UpdateCellConfigCommand(configs={B: {"disabled": True}})
    )
    await k.run([run(A, "x = 2")])
    assert "y" not in k.globals
    assert k.graph.cells[B].stale
    # B is edited to `y = x + 10` without a run before it is enabled.
    await k.set_cell_config(
        UpdateCellConfigCommand(configs={B: {"disabled": False}})
    )
    assert k.globals["y"] == 3


async def test_source_submitted_to_a_disabled_cell_is_adopted_not_run(
    k: Kernel,
) -> None:
    await k.run([run(A, "x = 1"), run(B, "y = x + 1")])
    await k.set_cell_config(
        UpdateCellConfigCommand(configs={A: {"disabled": True}})
    )
    await k.run([run(A, "x = 5")])
    assert k.graph.cells[A].code == "x = 5"
    assert k.cell_metadata[A].code == "x = 5"
    assert k.graph.cells[A].stale
    assert "x" not in k.globals
    await k.set_cell_config(
        UpdateCellConfigCommand(configs={A: {"disabled": False}})
    )
    assert k.globals["y"] == 6


async def test_a_syntax_error_keeps_the_adopted_source(k: Kernel) -> None:
    await k.run([run(A, "x = 1"), run(B, "y = x + 1")])
    await k.run([run(A, "x = (")])
    assert A not in k.graph.cells
    assert k.cell_metadata[A].code == "x = ("
    assert A not in k._uninstantiated_execution_requests
    assert A in k.errors
    assert "x" not in k.globals
    assert k.graph.cells[B].run_result_status == "exception"


async def test_markdown_cells_are_rendered_at_load_without_being_adopted(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k
    await load(k, (A, "import marimo as mo"), (B, 'mo.md("hello")'))
    assert set(k._uninstantiated_execution_requests) == {A}
    assert B not in k.graph.cells
    metadata = k.cell_metadata.get(B)
    assert metadata is None or metadata.code is None
    outputs = [
        op
        for op in mocked_kernel.stream.parsed_operations
        if getattr(op, "cell_id", None) == B
        and getattr(op, "output", None) is not None
    ]
    assert outputs


async def test_unrelated_cells_run_in_registration_order_which_drifts(
    k: Kernel,
) -> None:
    """Known looseness. Re-registering a cell moves it to the end."""
    await k.run(
        [
            run(C, "log = []"),
            run(A, 'log.append("a")'),
            run(B, 'log.append("b")'),
        ]
    )
    assert k.globals["log"] == ["a", "b"]
    await k.run([run(A, 'log.append("a")\nedited = True')])
    await k.run([run(C, "log = []")])
    assert k.globals["log"] == ["b", "a"]
