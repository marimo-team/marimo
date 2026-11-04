# Copyright 2026 Marimo. All rights reserved.
"""Execution lifecycles emitted by the kernel."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from inline_snapshot import snapshot

from marimo._messaging.notification import ExecutionNotification
from marimo._runtime.commands import (
    ExecuteCellCommand,
    ExecuteCellsCommand,
    ExecuteScratchpadCommand,
)
from marimo._runtime.kernel_request_handlers import KernelRequestHandlers
from marimo._types.ids import CellId_t
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
                "from marimo._runtime.commands import ExecuteCellCommand, ExecuteCellsCommand\n"
                f"await cm.get_context().execute_command(ExecuteCellsCommand(execution_requests=[ExecuteCellCommand(cell_id='child', code={failed_code!r})]))\n"
                "await cm.get_context().execute_command(ExecuteCellsCommand(execution_requests=[ExecuteCellCommand(cell_id='child', code='x = 42')]))\n"
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
            ExecuteScratchpadCommand(
                code="secret = 42", code_fingerprint="custom:secret"
            )
        )
    attempts = [
        m
        for m in MockStream(mocked_kernel.stream).parsed_operations
        if isinstance(m, ExecutionNotification)
    ]
    assert attempts[0].code_fingerprint == "custom:secret"
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
                "from marimo._runtime.commands import ExecuteCellCommand, ExecuteCellsCommand\n"
                "await cm.get_context().execute_command(ExecuteCellsCommand("
                "execution_requests=[ExecuteCellCommand(cell_id='parent', code='x = 1 / 0'), ExecuteCellCommand(cell_id='child', code='y = x')]))"
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
        "from marimo._runtime.commands import ExecuteCellCommand, ExecuteCellsCommand\n"
        "await cm.get_context().execute_command(ExecuteCellsCommand("
        "execution_requests=[ExecuteCellCommand(cell_id='b', code='print(x)')]))"
    )
    await KernelRequestHandlers(mocked_kernel.k)._handle_execute_scratchpad(
        ExecuteScratchpadCommand(
            run_id="nested",
            notebook_cells=(),
            code=(
                "import marimo._code_mode as cm\n"
                "from marimo._runtime.commands import ExecuteCellCommand, ExecuteCellsCommand\n"
                "await cm.get_context().execute_command(ExecuteCellsCommand("
                f"execution_requests=[ExecuteCellCommand(cell_id='a', code={inner!r}), ExecuteCellCommand(cell_id='b', code='print(x)')]))"
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
            execution_requests=[
                ExecuteCellCommand(
                    cell_id="a", code="x = 1 / 0", code_fingerprint="custom:a"
                ),
                ExecuteCellCommand(
                    cell_id="b", code=second, code_fingerprint="custom:b"
                ),
                ExecuteCellCommand(
                    cell_id="c", code="z = x + y", code_fingerprint="custom:c"
                ),
            ]
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
    assert planned["code_fingerprint"] == "custom:c"


@pytest.mark.parametrize(
    "code", ["x = 1", "x\u00a0= 1", "if !!!", "x = 1 / 0"]
)
@pytest.mark.parametrize("mode", ["edit", "run"])
async def test_submitted_fingerprint_survives_execution(
    mocked_kernel: MockedKernel, code: str, mode: str
) -> None:
    with patch("marimo._runtime.execution.get_mode", return_value=mode):
        await KernelRequestHandlers(mocked_kernel.k)._handle_execute_multiple(
            ExecuteCellsCommand(
                execution_requests=[
                    ExecuteCellCommand(
                        cell_id=CellId_t("a"),
                        code=code,
                        code_fingerprint="custom:v1:a",
                    )
                ]
            )
        )
    planned = [
        (m.cell_id, m.code, m.code_fingerprint)
        for m in MockStream(mocked_kernel.stream).parsed_operations
        if isinstance(m, ExecutionNotification) and m.phase == "planned"
    ]
    assert planned == [("a", code if mode == "edit" else None, "custom:v1:a")]


async def test_reactive_runs_retain_fingerprints_and_edits_replace_them(
    mocked_kernel: MockedKernel,
) -> None:
    handlers = KernelRequestHandlers(mocked_kernel.k)
    await handlers._handle_execute_multiple(
        ExecuteCellsCommand(
            execution_requests=[
                ExecuteCellCommand(
                    cell_id=CellId_t("a"),
                    code="x = 1",
                    code_fingerprint="custom:a1",
                ),
                ExecuteCellCommand(
                    cell_id=CellId_t("b"),
                    code="y = x + 1",
                    code_fingerprint="custom:b1",
                ),
            ]
        )
    )
    await handlers._handle_execute_multiple(
        ExecuteCellsCommand(
            execution_requests=[
                ExecuteCellCommand(
                    cell_id=CellId_t("a"),
                    code="x = 2",
                    code_fingerprint="custom:a2",
                )
            ]
        )
    )
    # A new submission can change identity without changing the source.
    await handlers._handle_execute_multiple(
        ExecuteCellsCommand(
            execution_requests=[
                ExecuteCellCommand(
                    cell_id=CellId_t("b"),
                    code="y = x + 1",
                    code_fingerprint="custom:b2",
                )
            ]
        )
    )
    planned = [
        (m.cell_id, m.code_fingerprint)
        for m in MockStream(mocked_kernel.stream).parsed_operations
        if isinstance(m, ExecutionNotification) and m.phase == "planned"
    ]
    assert planned == [
        ("a", "custom:a1"),
        ("b", "custom:b1"),
        ("a", "custom:a2"),
        ("b", "custom:b1"),
        ("b", "custom:b2"),
    ]


async def test_pending_ancestor_retains_submitted_fingerprint(
    mocked_kernel: MockedKernel,
) -> None:
    kernel = mocked_kernel.k
    kernel._uninstantiated_execution_requests[CellId_t("a")] = (
        ExecuteCellCommand(
            cell_id=CellId_t("a"), code="x = 1", code_fingerprint="custom:a"
        )
    )
    await kernel.run(
        [
            ExecuteCellCommand(
                cell_id=CellId_t("b"),
                code="y = x",
                code_fingerprint="custom:b",
            )
        ]
    )
    planned = [
        (m.cell_id, m.code_fingerprint)
        for m in MockStream(mocked_kernel.stream).parsed_operations
        if isinstance(m, ExecutionNotification) and m.phase == "planned"
    ]
    assert planned == [("a", "custom:a"), ("b", "custom:b")]
