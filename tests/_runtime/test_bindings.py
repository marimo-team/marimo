# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from typing import TYPE_CHECKING

import pytest

from marimo._core.protocol import ExecutionId, Revision
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.notification import (
    ExecutionNotification,
    VariableValue,
    VariableValuesNotification,
)
from marimo._runtime import runtime
from marimo._runtime.commands import (
    DeleteCellCommand,
    ExecuteCellsCommand,
    ExecuteScratchpadCommand,
    UpdateCellConfigCommand,
    UpdateUIElementCommand,
)
from marimo._session.model import SessionMode
from marimo._types.ids import CellId_t
from tests._runtime._helpers.session import mocked_kernel_session

if TYPE_CHECKING:
    from collections.abc import Iterator

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


@pytest.mark.parametrize("debugging", [False, True])
async def test_reimport_in_the_same_cell_keeps_its_revision(
    mocked_kernel: MockedKernel,
    monkeypatch: pytest.MonkeyPatch,
    debugging: bool,
) -> None:
    if debugging:
        monkeypatch.setenv("DEBUGPY_RUNNING", "1")
    await run(mocked_kernel.k, a="import math", b="value = math.pi")
    messages = mocked_kernel.stream.parsed_operations
    before = completed(messages)["b"]
    old = bound(messages)["math"]

    await run(mocked_kernel.k, a="import math\nimport os")
    messages = mocked_kernel.stream.parsed_operations
    current = bound(messages)["math"]
    assert current.execution_id != old.execution_id
    assert current.revision == old.revision
    assert completed(messages)["b"].depends_on == before.depends_on


async def test_rebinding_none_in_the_same_cell_advances_its_revision(
    mocked_kernel: MockedKernel,
) -> None:
    await run(mocked_kernel.k, a="x = None")
    old = bound(mocked_kernel.stream.parsed_operations)["x"].revision
    await run(mocked_kernel.k, a="x = None\ny = 1")
    new = bound(mocked_kernel.stream.parsed_operations)["x"].revision
    assert new != old


@pytest.mark.parametrize(
    "replacement", ["pass", "import missing_revision_test_module\nimport math"]
)
async def test_removed_or_failed_imports_do_not_reuse_their_old_revision(
    mocked_kernel: MockedKernel,
    replacement: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = mocked_kernel.k
    await run(kernel, a="import math")
    old = bound(mocked_kernel.stream.parsed_operations)["math"].revision
    await run(kernel, a=replacement)
    if replacement == "pass":
        await run(kernel, a="import math")
    else:
        module = ModuleType("missing_revision_test_module")
        monkeypatch.setitem(sys.modules, module.__name__, module)
        await run(kernel, a=replacement)
    assert (
        bound(mocked_kernel.stream.parsed_operations)["math"].revision != old
    )


@pytest.mark.parametrize("changed", [False, True])
async def test_queued_imports_use_the_latest_nested_result(
    mocked_kernel: MockedKernel,
    monkeypatch: pytest.MonkeyPatch,
    changed: bool,
) -> None:
    module = ModuleType("revision_test_module")
    module.value = None
    monkeypatch.setitem(sys.modules, module.__name__, module)
    kernel = mocked_kernel.k
    kernel.reactive_execution_mode = "lazy"
    code = "from revision_test_module import value"
    nested = False

    async def rerun_import() -> None:
        if nested:
            if changed:
                module.value = object()
            await run(kernel, b=code)

    kernel.globals["rerun_import"] = rerun_import
    await run(kernel, a="await rerun_import()", b=code, c="result = value")
    initial = bound(mocked_kernel.stream.parsed_operations)["value"].revision
    reader = completed(mocked_kernel.stream.parsed_operations)["c"]
    nested = True
    mocked_kernel.stream.messages.clear()
    await run(kernel, a="await rerun_import()", b=code)
    messages = mocked_kernel.stream.parsed_operations
    values = [
        v
        for m in messages
        if isinstance(m, VariableValuesNotification)
        for v in m.variables
        if v.name == "value" and v.value is not None
    ]
    assert len(values) == 2
    assert values[0].execution_id != values[1].execution_id
    assert values[0].revision == values[1].revision
    assert (values[1].revision != initial) is changed
    assert "c" not in completed(messages)
    assert reader.depends_on == {"value": initial}


async def test_disabled_imports_discard_their_carried_revision(
    mocked_kernel: MockedKernel,
) -> None:
    kernel = mocked_kernel.k
    kernel.reactive_execution_mode = "lazy"
    await run(kernel, a="import math")
    old = bound(mocked_kernel.stream.parsed_operations)["math"].revision
    await kernel.router.dispatch(
        UpdateCellConfigCommand(configs={CellId_t("a"): {"disabled": True}})
    )
    await run(kernel, a="import math\nimport os")
    await kernel.router.dispatch(
        UpdateCellConfigCommand(configs={CellId_t("a"): {"disabled": False}})
    )
    await run(kernel, a="import math\nimport os")
    assert (
        bound(mocked_kernel.stream.parsed_operations)["math"].revision != old
    )


async def test_rejected_imports_discard_their_carried_revision(
    mocked_kernel: MockedKernel,
) -> None:
    kernel = mocked_kernel.k
    await run(kernel, a="import math")
    old = bound(mocked_kernel.stream.parsed_operations)["math"].revision
    await run(kernel, a="import math\nimport os", b="math = 1")
    await kernel.delete_cell(DeleteCellCommand(cell_id=CellId_t("b")))
    await run(kernel, a="import math\nimport os")
    assert (
        bound(mocked_kernel.stream.parsed_operations)["math"].revision != old
    )


async def test_preview_can_wait_for_a_state_setter(
    mocked_kernel: MockedKernel,
) -> None:
    kernel = mocked_kernel.k
    kernel.reactive_execution_mode = "lazy"
    await run(
        kernel,
        a="import marimo as mo",
        b="get, set_value = mo.state(0)",
        c="""
class _Preview:
    __slots__ = ()

    def __str__(self):
        thread = mo.Thread(target=lambda: set_value(1))
        thread.start()
        thread.join(timeout=1)
        return "blocked" if thread.is_alive() else "done"

x = _Preview()
""",
    )
    assert (
        variables(mocked_kernel.stream.parsed_operations)["x"].value == "done"
    )


async def test_preview_cannot_overwrite_an_update_during_rendering(
    mocked_kernel: MockedKernel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = mocked_kernel.k
    kernel.reactive_execution_mode = "lazy"
    await run(
        kernel, a="import marimo as mo", b="get, set_value = mo.state(0)"
    )
    old = bound(mocked_kernel.stream.parsed_operations)["get"]
    mocked_kernel.stream.messages.clear()
    create_preview = runtime.create_variable_value
    rendered = False

    def render(name: str, value: object) -> VariableValue:
        nonlocal rendered
        preview = create_preview(name, value)
        if name == "get":
            preview.value = str(kernel.globals["get"]())
            if not rendered:
                rendered = True
                # The update must be visible before formatting can run user code.
                assert bound(mocked_kernel.stream.parsed_operations)[
                    "get"
                ].revision == Revision(ExecutionId(old.execution_id), 1)
                kernel.globals["set_value"](2)
        return preview

    monkeypatch.setattr(runtime, "create_variable_value", render)
    kernel.globals["set_value"](1)
    assert variables(mocked_kernel.stream.parsed_operations)[
        "get"
    ] == VariableValue(
        name="get",
        value="2",
        datatype="State",
        execution_id=old.execution_id,
        revision=Revision(ExecutionId(old.execution_id), 2),
    )


@pytest.fixture
def isolated_duckdb() -> Iterator[None]:
    import duckdb

    duckdb.begin()
    try:
        yield
    finally:
        duckdb.rollback()


@pytest.mark.usefixtures("isolated_duckdb")
@pytest.mark.skipif(
    not DependencyManager.duckdb.has() or not DependencyManager.sqlglot.has(),
    reason="SQL dependencies not installed",
)
@pytest.mark.parametrize("kind", ["TABLE", "VIEW", "TEMP TABLE"])
@pytest.mark.parametrize("qualified", [False, True])
async def test_sql_bindings_record_inputs_and_replacement(
    mocked_kernel: MockedKernel, kind: str, qualified: bool
) -> None:
    kernel = mocked_kernel.k
    kernel.reactive_execution_mode = "lazy"
    await run(kernel, a="import duckdb")
    leaf = f"revision_{kind.lower().replace(' ', '_')}"
    name = f"main.{leaf}" if qualified else leaf
    producer = (
        f"duckdb.sql('CREATE OR REPLACE {kind} {name} AS SELECT 1 AS x')"
    )
    reader = f"df = duckdb.sql('SELECT * FROM {name}').fetchall()"
    await run(kernel, b=producer, c=reader)
    messages = mocked_kernel.stream.parsed_operations
    values = bound(messages)
    table = values[name]
    assert table == VariableValue(
        name=name,
        value=None,
        datatype=kind.rsplit(maxsplit=1)[-1].lower(),
        execution_id=completed(messages)["b"].execution_id,
        revision=Revision(
            ExecutionId(completed(messages)["b"].execution_id), 0
        ),
    )
    assert completed(messages)["c"].depends_on == {
        "duckdb": values["duckdb"].revision,
        name: table.revision,
    }
    await run(kernel, b=producer.replace("SELECT 1", "SELECT 2"))
    assert (
        bound(mocked_kernel.stream.parsed_operations)[name].revision
        != table.revision
    )
    assert kernel.globals["df"] == [(1,)]


@pytest.mark.usefixtures("isolated_duckdb")
@pytest.mark.skipif(
    not DependencyManager.duckdb.has() or not DependencyManager.sqlglot.has(),
    reason="SQL dependencies not installed",
)
async def test_sql_bindings_only_include_existing_objects(
    mocked_kernel: MockedKernel,
) -> None:
    kernel = mocked_kernel.k
    kernel.reactive_execution_mode = "lazy"
    await run(
        kernel,
        a="import duckdb",
        b="""
duckdb.sql('CREATE TABLE revision_exists AS SELECT 1 AS x')
if False:
    duckdb.sql('CREATE TABLE revision_skipped AS SELECT 1 AS x')
raise RuntimeError('partial execution')
duckdb.sql('CREATE TABLE revision_failed AS SELECT 1 AS x')
""",
    )
    assert set(bound(mocked_kernel.stream.parsed_operations)) == {
        "duckdb",
        "revision_exists",
    }
    await kernel.delete_cell(DeleteCellCommand(cell_id=CellId_t("b")))
    mocked_kernel.stream.messages.clear()
    await run(kernel, c="duckdb.sql('SELECT * FROM revision_exists')")
    assert (
        completed(mocked_kernel.stream.parsed_operations)["c"].depends_on[
            "revision_exists"
        ]
        is None
    )


@pytest.mark.usefixtures("isolated_duckdb")
@pytest.mark.skipif(
    not DependencyManager.duckdb.has() or not DependencyManager.sqlglot.has(),
    reason="SQL dependencies not installed",
)
async def test_sql_qualified_bindings_do_not_collide(
    mocked_kernel: MockedKernel,
) -> None:
    kernel = mocked_kernel.k
    kernel.reactive_execution_mode = "lazy"
    await run(
        kernel,
        a="import duckdb",
        b="duckdb.sql('CREATE SCHEMA IF NOT EXISTS revision_left')",
        c="duckdb.sql('CREATE SCHEMA IF NOT EXISTS revision_right')",
        d="duckdb.sql('CREATE TABLE revision_left.t AS SELECT 1 AS x')",
        e="duckdb.sql('CREATE TABLE revision_right.t AS SELECT 2 AS x')",
        f="rows = duckdb.sql('SELECT * FROM revision_left.t').fetchall()",
    )
    messages = mocked_kernel.stream.parsed_operations
    values = bound(messages)
    assert completed(messages)["f"].depends_on == {
        name: values[name].revision
        for name in ("duckdb", "revision_left", "revision_left.t")
    }
    assert kernel.globals["rows"] == [(1,)]
    assert (
        values["revision_right.t"].execution_id
        == completed(messages)["e"].execution_id
    )

    await run(kernel, g="duckdb.sql('DROP TABLE revision_left.t')")
    mocked_kernel.stream.messages.clear()
    await run(
        kernel,
        f="rows = duckdb.sql('SELECT * FROM revision_left.t').fetchall()",
    )
    assert completed(mocked_kernel.stream.parsed_operations)[
        "f"
    ].depends_on == {
        "duckdb": values["duckdb"].revision,
        "revision_left": values["revision_left"].revision,
        "revision_left.t": None,
    }
