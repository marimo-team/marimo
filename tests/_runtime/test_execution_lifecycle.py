# Copyright 2026 Marimo. All rights reserved.
"""Execution lifecycles emitted by the kernel."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from inline_snapshot import snapshot

from marimo._messaging.notification import ExecutionNotification
from marimo._runtime.commands import (
    ExecuteCellsCommand,
    ExecuteScratchpadCommand,
)
from marimo._runtime.kernel_request_handlers import KernelRequestHandlers
from tests._messaging.mocks import MockStream

if TYPE_CHECKING:
    from tests.conftest import MockedKernel


@pytest.mark.parametrize("code", ["3 * 3", "if !!!"])
async def test_scratch_is_planned_before_compilation(
    mocked_kernel: MockedKernel, code: str
) -> None:
    kernel = mocked_kernel.k
    compile_cell = kernel._try_compiling_cell

    def compile_after_planning(*args: Any, **kwargs: Any) -> Any:
        messages = MockStream(mocked_kernel.stream).operations
        assert [
            (m["op"], m.get("phase"), m.get("code")) for m in messages
        ] == [("execution", "planned", code)]
        return compile_cell(*args, **kwargs)

    with patch.object(
        kernel, "_try_compiling_cell", side_effect=compile_after_planning
    ):
        await KernelRequestHandlers(kernel)._handle_execute_scratchpad(
            ExecuteScratchpadCommand(code=code)
        )


@pytest.mark.parametrize("failed_code", ["if !!!", "1 / 0"])
async def test_a_retry_has_its_own_identity_and_source(
    mocked_kernel: MockedKernel, failed_code: str
) -> None:
    await KernelRequestHandlers(mocked_kernel.k)._handle_execute_scratchpad(
        ExecuteScratchpadCommand(
            run_id="retry",
            notebook_cells=(),
            code=(
                "import marimo._code_mode as cm\n"
                "from marimo._runtime.commands import ExecuteCellsCommand\n"
                f"await cm.get_context().execute_command(ExecuteCellsCommand(cell_ids=['child'], codes=[{failed_code!r}]))\n"
                "await cm.get_context().execute_command(ExecuteCellsCommand(cell_ids=['child'], codes=['x = 42']))\n"
            ),
        )
    )
    messages = MockStream(mocked_kernel.stream).parsed_operations
    attempts = [
        m
        for m in messages
        if isinstance(m, ExecutionNotification) and m.cell_id == "child"
    ]
    planned = [m for m in attempts if m.phase == "planned"]
    assert len({m.execution_id for m in planned}) == 2
    assert [(m.phase, m.code) for m in attempts] == (
        [("planned", failed_code)]
        + ([] if failed_code == "if !!!" else [("running", None)])
        + [
            ("completed", None),
            ("planned", "x = 42"),
            ("running", None),
            ("completed", None),
        ]
    )
    assert {m.run_id for m in attempts} == {"retry"}


@pytest.mark.parametrize("mode", ["edit", "run"])
async def test_execution_source_is_private_in_app_mode(
    mocked_kernel: MockedKernel, mode: str
) -> None:
    with patch("marimo._runtime.execution.get_mode", return_value=mode):
        await KernelRequestHandlers(
            mocked_kernel.k
        )._handle_execute_scratchpad(
            ExecuteScratchpadCommand(code="secret = 42")
        )
    attempts = [
        m
        for m in MockStream(mocked_kernel.stream).parsed_operations
        if isinstance(m, ExecutionNotification)
    ]
    assert [m.code for m in attempts] == [
        "secret = 42" if mode == "edit" else None,
        None,
        None,
    ]


async def test_skipped_attempt_completes_without_starting(
    mocked_kernel: MockedKernel,
) -> None:
    await KernelRequestHandlers(mocked_kernel.k)._handle_execute_scratchpad(
        ExecuteScratchpadCommand(
            run_id="skipped",
            notebook_cells=(),
            code=(
                "import marimo._code_mode as cm\n"
                "from marimo._runtime.commands import ExecuteCellsCommand\n"
                "await cm.get_context().execute_command(ExecuteCellsCommand("
                "cell_ids=['parent', 'child'], codes=['x = 1 / 0', 'y = x']))"
            ),
        )
    )
    messages = MockStream(mocked_kernel.stream).operations
    child = [m for m in messages if m.get("cell_id") == "child"]
    assert [m["phase"] for m in child if m["op"] == "execution"] == snapshot(
        ["planned", "completed"]
    )
    planned = next(m for m in child if m.get("phase") == "planned")
    error = next(m for m in child if m.get("output"))
    assert error["execution_id"] == planned["execution_id"]
    assert child[-1]["phase"] == "completed"


async def test_nested_commands_can_evaluate_an_outer_queued_cell(
    mocked_kernel: MockedKernel,
) -> None:
    inner = (
        "x = 42\n"
        "import marimo._code_mode as cm\n"
        "from marimo._runtime.commands import ExecuteCellsCommand\n"
        "await cm.get_context().execute_command(ExecuteCellsCommand("
        "cell_ids=['b'], codes=['print(x)']))"
    )
    await KernelRequestHandlers(mocked_kernel.k)._handle_execute_scratchpad(
        ExecuteScratchpadCommand(
            run_id="nested",
            notebook_cells=(),
            code=(
                "import marimo._code_mode as cm\n"
                "from marimo._runtime.commands import ExecuteCellsCommand\n"
                "await cm.get_context().execute_command(ExecuteCellsCommand("
                f"cell_ids=['a', 'b'], codes=[{inner!r}, 'print(x)']))"
            ),
        )
    )
    attempts = [
        m
        for m in MockStream(mocked_kernel.stream).parsed_operations
        if isinstance(m, ExecutionNotification) and m.cell_id == "b"
    ]
    assert [m.phase for m in attempts] == snapshot(
        ["planned", "running", "completed", "planned", "running", "completed"]
    )
    assert len({m.execution_id for m in attempts}) == 2


@pytest.mark.parametrize("second", ["y = 1 / 0", "raise KeyboardInterrupt"])
async def test_skipped_attempt_can_report_multiple_errors(
    mocked_kernel: MockedKernel, second: str
) -> None:
    await KernelRequestHandlers(mocked_kernel.k)._handle_execute_multiple(
        ExecuteCellsCommand(
            cell_ids=["a", "b", "c"],
            codes=["x = 1 / 0", second, "z = x + y"],
        )
    )
    messages = [
        m
        for m in MockStream(mocked_kernel.stream).operations
        if m.get("cell_id") == "c"
    ]
    assert [
        m["phase"] for m in messages if m["op"] == "execution"
    ] == snapshot(["planned", "completed"])
    errors = [m for m in messages if m.get("output")]
    assert len(errors) == 2
    planned = next(m for m in messages if m.get("phase") == "planned")
    assert {m["execution_id"] for m in errors} == {planned["execution_id"]}
