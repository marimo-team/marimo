# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from marimo._messaging.notification import (
    ExecutionNotification,
    VariableValue,
    VariableValuesNotification,
)
from marimo._runtime.commands import (
    DeleteCellCommand,
    ExecuteCellsCommand,
    ExecuteScratchpadCommand,
    UpdateUIElementCommand,
)
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


async def test_state_updates_advance_the_setters_own_input_revision(
    mocked_kernel: MockedKernel,
) -> None:
    await run(
        mocked_kernel.k,
        a="import marimo as mo",
        b="get, set_value = mo.state(0)",
        c="value = get()",
    )
    old = bound(mocked_kernel.stream.parsed_operations)["get"].revision
    mocked_kernel.stream.messages.clear()

    await run(
        mocked_kernel.k,
        d="for i in range(3):\n    set_value(get() + 1)",
    )
    messages = mocked_kernel.stream.parsed_operations
    new = bound(messages)["get"].revision
    assert new.execution == old.execution
    assert new.update == old.update + 3
    executions = completed(messages)
    assert executions["d"].depends_on["get"] == new
    assert executions["c"].depends_on == {"get": new}
    assert mocked_kernel.k.globals["value"] == 3


async def test_ui_updates_publish_revisions_without_rerunning_lazy_cells(
    mocked_kernel: MockedKernel,
) -> None:
    kernel = mocked_kernel.k
    kernel.reactive_execution_mode = "lazy"
    await run(
        kernel,
        a="import marimo as mo",
        b="slider = mo.ui.slider(0, 10, value=1)",
        c="value = slider.value",
    )
    messages = mocked_kernel.stream.parsed_operations
    before = completed(messages)["c"]
    old = bound(messages)["slider"].revision

    await kernel.router.dispatch(
        UpdateUIElementCommand.from_ids_and_values(
            [(kernel.globals["slider"]._id, 5)]
        )
    )
    messages = mocked_kernel.stream.parsed_operations
    assert completed(messages)["c"] == before
    slider = bound(messages)["slider"]
    assert (slider.revision.execution, slider.revision.update) == (
        old.execution,
        old.update + 1,
    )
    assert slider.value == "5"
    assert before.depends_on == {"slider": old}


async def test_scratch_updates_reach_nested_readers_from_the_notebook_namespace(
    mocked_kernel: MockedKernel,
) -> None:
    kernel = mocked_kernel.k
    kernel.reactive_execution_mode = "lazy"
    await run(
        kernel,
        a="import marimo as mo",
        b="get, set_value = mo.state(1)",
        c="value = get()",
        alias="alias = get",
    )
    before = bound(mocked_kernel.stream.parsed_operations)["get"]

    async def run_reader() -> None:
        await run(kernel, c="value = get()")

    kernel.globals["run_reader"] = run_reader
    mocked_kernel.stream.messages.clear()
    await kernel.router.dispatch(
        ExecuteScratchpadCommand(
            code="""
get = "scratch-local"
set_value(2)
await run_reader()
"""
        )
    )
    messages = mocked_kernel.stream.parsed_operations
    updated = bound(messages)
    after = updated["get"]
    assert updated["alias"].revision.update == 1
    assert after.datatype == "State"
    assert after.execution_id == before.execution_id
    assert after.revision.update == before.revision.update + 1
    child = completed(messages)["c"]
    assert child.depends_on == {"get": after.revision}
    update_index = next(
        i
        for i, m in enumerate(messages)
        if isinstance(m, VariableValuesNotification) and after in m.variables
    )
    child_start = next(
        i
        for i, m in enumerate(messages)
        if isinstance(m, ExecutionNotification)
        and m.execution_id == child.execution_id
        and m.phase == "running"
    )
    assert update_index < child_start
    assert kernel.globals["value"] == 2


async def test_background_updates_do_not_rewrite_completed_inputs(
    mocked_kernel: MockedKernel,
) -> None:
    kernel = mocked_kernel.k
    kernel.reactive_execution_mode = "lazy"
    await run(
        kernel,
        a="import marimo as mo\nimport threading",
        b="get, set_value = mo.state(1)",
        c="""
gate = threading.Event()
done = threading.Event()
def _update():
    gate.wait()
    set_value(2)
    done.set()
worker = mo.Thread(target=_update)
worker.start()
get()
""",
    )
    before = completed(mocked_kernel.stream.parsed_operations)["c"]
    try:
        kernel.globals["gate"].set()
        assert await asyncio.to_thread(kernel.globals["done"].wait, 5)
    finally:
        kernel.globals["gate"].set()
        kernel.globals["worker"].join(timeout=5)
    messages = mocked_kernel.stream.parsed_operations
    assert completed(messages)["c"] == before
    previous = before.depends_on["get"]
    current = bound(messages)["get"].revision
    assert (current.execution, current.update) == (
        previous.execution,
        previous.update + 1,
    )
