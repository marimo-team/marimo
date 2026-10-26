# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from marimo._messaging.notification import (
    ExecutionNotification,
    VariableValue,
    VariableValuesNotification,
)
from marimo._runtime.commands import DeleteCellCommand, ExecuteCellsCommand
from marimo._session.model import SessionMode
from marimo._types.ids import CellId_t
from tests._runtime._helpers.session import mocked_kernel_session

if TYPE_CHECKING:
    from marimo._config.config import ExecutionType
    from marimo._messaging.notification import NotificationMessage
    from marimo._runtime.runtime import Kernel
    from tests.conftest import MockedKernel


async def run(kernel: Kernel, **cells: str) -> None:
    await kernel.router.dispatch(
        ExecuteCellsCommand(
            cell_ids=[CellId_t(cid) for cid in cells],
            codes=list(cells.values()),
        )
    )


def completed(
    messages: list[NotificationMessage],
) -> dict[CellId_t, ExecutionNotification]:
    return {
        m.cell_id: m
        for m in messages
        if isinstance(m, ExecutionNotification) and m.phase == "completed"
    }


def variables(messages: list[NotificationMessage]) -> dict[str, VariableValue]:
    return {
        v.name: v
        for m in messages
        if isinstance(m, VariableValuesNotification)
        for v in m.variables
    }


def bound(messages: list[NotificationMessage]) -> dict[str, VariableValue]:
    return {
        name: v
        for name, v in variables(messages).items()
        if v.revision is not None
    }


@pytest.mark.parametrize("execution_type", ["relaxed", "strict"])
async def test_conditional_definitions_bind_only_defined_names(
    mocked_kernel: MockedKernel, execution_type: ExecutionType
) -> None:
    mocked_kernel.k.execution_type = execution_type
    await run(
        mocked_kernel.k,
        a="flag = False",
        b="if flag:\n    x = 1\ny = None",
    )
    messages = mocked_kernel.stream.parsed_operations
    values = variables(messages)
    assert set(bound(messages)) == {"flag", "y"}
    assert values["x"].execution_id is None
    assert completed(messages)["b"].depends_on == {
        "flag": values["flag"].revision
    }


async def test_run_mode_reports_no_variables() -> None:
    with mocked_kernel_session(mode=SessionMode.RUN) as session:
        await run(session.kernel, a="secret = 'private'", b="len(secret)")
        messages = session.stream.parsed_operations
        assert not variables(messages)
        assert all(
            m.depends_on is None
            for m in messages
            if isinstance(m, ExecutionNotification)
        )


async def test_bindings_are_reported_before_completion(
    mocked_kernel: MockedKernel,
) -> None:
    await run(
        mocked_kernel.k,
        a="x = 1",
        b="y = print(x + 1)",
        c="z = missing",
    )
    messages = mocked_kernel.stream.parsed_operations
    executions = completed(messages)
    values = bound(messages)
    assert set(values) == {"x", "y"}
    assert executions["b"].depends_on == {
        "print": None,
        "x": values["x"].revision,
    }
    assert executions["c"].depends_on == {"missing": None}
    assert values["x"].value == "1"
    assert values["x"].execution_id == executions["a"].execution_id
    for value in values.values():
        reported = next(
            i
            for i, m in enumerate(messages)
            if isinstance(m, VariableValuesNotification)
            and value in m.variables
        )
        completion = next(
            i
            for i, m in enumerate(messages)
            if isinstance(m, ExecutionNotification)
            and m.execution_id == value.execution_id
            and m.phase == "completed"
        )
        assert reported < completion


async def test_lazy_rerun_replaces_a_binding_without_rewriting_old_inputs(
    mocked_kernel: MockedKernel,
) -> None:
    kernel = mocked_kernel.k
    kernel.reactive_execution_mode = "lazy"
    await run(kernel, a="x = 1", b="y = x + 1")
    messages = mocked_kernel.stream.parsed_operations
    before = completed(messages)["b"]
    revision = bound(messages)["x"].revision

    await run(kernel, a="x = 2")
    messages = mocked_kernel.stream.parsed_operations
    assert completed(messages)["b"] == before
    assert before.depends_on == {"x": revision}
    assert bound(messages)["x"].revision != revision

    await run(kernel, b="y = x + 1")
    messages = mocked_kernel.stream.parsed_operations
    assert completed(messages)["b"].depends_on == {
        "x": bound(messages)["x"].revision
    }


@pytest.mark.parametrize("deletion", ["cell", "python"])
async def test_deleted_bindings_are_unbound_for_later_readers(
    mocked_kernel: MockedKernel,
    deletion: str,
) -> None:
    kernel = mocked_kernel.k
    kernel.reactive_execution_mode = "lazy"
    await run(kernel, a="x = 1", b="y = x + 1")
    if deletion == "cell":
        await kernel.delete_cell(DeleteCellCommand(cell_id=CellId_t("a")))
    else:
        await run(kernel, d="del x")
    mocked_kernel.stream.messages.clear()
    await run(kernel, b="y = x + 1")
    messages = mocked_kernel.stream.parsed_operations
    assert completed(messages)["b"].depends_on == {"x": None}
    assert not bound(messages)


@pytest.mark.parametrize("failure", ["1 / 0", "raise KeyboardInterrupt"])
async def test_failed_and_skipped_executions_only_bind_existing_names(
    mocked_kernel: MockedKernel,
    failure: str,
) -> None:
    await run(mocked_kernel.k, a=f"x = 1\n{failure}\ny = 2", b="z = y")
    messages = mocked_kernel.stream.parsed_operations
    executions = completed(messages)
    assert set(executions) == {"a", "b"}
    assert set(bound(messages)) == {"x"}
    assert variables(messages)["y"].revision is None
    assert executions["b"].depends_on == {"y": None}
