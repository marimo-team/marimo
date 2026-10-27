# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.commands import DeleteCellCommand, UpdateCellConfigCommand
from marimo._runtime.runtime import Kernel
from marimo._types.ids import CellId_t
from tests.conftest import ExecReqProvider

pytestmark = pytest.mark.skipif(
    not DependencyManager.duckdb.has() or not DependencyManager.sqlglot.has(),
    reason="SQL dependencies required",
)


def require_nested_schemas() -> None:
    from marimo._sql.utils import is_duckdb_v2

    if not is_duckdb_v2():
        pytest.skip("Nested schemas require DuckDB 2")


@pytest.mark.parametrize("separate_cells", [False, True])
async def test_catalog_rebinding_reruns_query_on_attach_and_detach(
    k: Kernel, exec_req: ExecReqProvider, separate_cells: bool
) -> None:
    import duckdb

    require_nested_schemas()
    alias = "runner_catalog_rebinding"
    try:
        duckdb.execute(
            f"CREATE SCHEMA memory.{alias}; CREATE SCHEMA memory.{alias}.main"
        )
        await k.run(
            [
                exec_req.get("import marimo as mo\nimport duckdb"),
                exec_req.get_with_id(
                    "memory_table",
                    f'mo.sql("CREATE TABLE memory.{alias}.main.sales AS SELECT 1 AS amount")',
                ),
                exec_req.get_with_id(
                    "query",
                    f'rows = duckdb.sql("SELECT * FROM {alias}.main.sales").fetchall()',
                ),
            ]
        )
        assert not k.errors
        assert k.globals["rows"] == [(1,)]
        assert "memory_table" in k.graph.parents["query"]

        attach_sql = f"ATTACH ':memory:' AS {alias}"
        table_sql = f"CREATE TABLE {alias}.main.sales AS SELECT 2 AS amount"
        if separate_cells:
            requests = [
                exec_req.get_with_id("attached", f"mo.sql({attach_sql!r})"),
                exec_req.get_with_id(
                    "attached_table", f"mo.sql({table_sql!r})"
                ),
            ]
            relation_parent = "attached_table"
        else:
            requests = [
                exec_req.get_with_id(
                    "attached", f"mo.sql({f'{attach_sql}; {table_sql}'!r})"
                )
            ]
            relation_parent = "attached"
        await k.run(requests)
        assert not k.errors
        assert k.globals["rows"] == [(2,)]
        assert relation_parent in k.graph.parents["query"]
        assert "memory_table" not in k.graph.parents["query"]
        assert duckdb.sql(
            f"SELECT amount FROM memory.{alias}.main.sales"
        ).fetchone() == (1,)

        if separate_cells:
            await k.delete_cell(
                DeleteCellCommand(cell_id=CellId_t("attached_table"))
            )
        await k.delete_cell(DeleteCellCommand(cell_id=CellId_t("attached")))

        assert not k.errors
        assert k.globals["rows"] == [(1,)]
        assert "memory_table" in k.graph.parents["query"]
        assert "attached" not in k.graph.parents["query"]
    finally:
        duckdb.execute(f"DETACH DATABASE IF EXISTS {alias}")
        duckdb.execute(f"DROP SCHEMA IF EXISTS memory.{alias} CASCADE")


async def test_disabled_table_cleanup_keeps_its_original_catalog_binding(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    import duckdb

    require_nested_schemas()
    alias = "runner_deferred_catalog"
    try:
        duckdb.execute(
            f"CREATE SCHEMA memory.{alias}; CREATE SCHEMA memory.{alias}.main; "
            f"CREATE TABLE memory.{alias}.main.sales AS SELECT 1 AS amount"
        )
        await k.run(
            [
                exec_req.get("import marimo as mo"),
                exec_req.get_with_id(
                    "attached", f"mo.sql(\"ATTACH ':memory:' AS {alias}\")"
                ),
                exec_req.get_with_id(
                    "table",
                    f'mo.sql("CREATE TABLE {alias}.main.sales AS SELECT 2 AS amount")',
                ),
            ]
        )
        assert not k.errors
        assert duckdb.sql(f"SELECT * FROM {alias}.main.sales").fetchone() == (
            2,
        )
        await k.set_cell_config(
            UpdateCellConfigCommand(
                configs={CellId_t("table"): {"disabled": True}}
            )
        )
        await k.delete_cell(DeleteCellCommand(cell_id=CellId_t("attached")))
        assert duckdb.sql(
            f"SELECT * FROM memory.{alias}.main.sales"
        ).fetchone() == (1,)

        await k.delete_cell(DeleteCellCommand(cell_id=CellId_t("table")))

        assert duckdb.sql(
            f"SELECT * FROM memory.{alias}.main.sales"
        ).fetchone() == (1,)
    finally:
        duckdb.execute(f"DETACH DATABASE IF EXISTS {alias}")
        duckdb.execute(f"DROP SCHEMA IF EXISTS memory.{alias} CASCADE")


async def test_failed_catalog_rebinding_does_not_own_existing_memory_table(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    import duckdb

    require_nested_schemas()
    alias = "runner_failed_catalog"
    try:
        duckdb.execute(
            f"CREATE SCHEMA memory.{alias}; CREATE SCHEMA memory.{alias}.main; "
            f"CREATE TABLE memory.{alias}.main.sales AS SELECT 1 AS amount"
        )
        await k.run(
            [
                exec_req.get("import marimo as mo"),
                exec_req.get_with_id(
                    "attached", f"mo.sql(\"ATTACH ':memory:' AS {alias}\")"
                ),
                exec_req.get_with_id(
                    "table",
                    f'mo.sql("CREATE TABLE {alias}.main.sales AS SELECT 2 AS amount")',
                ),
            ]
        )
        assert not k.errors
        assert duckdb.sql(f"SELECT * FROM {alias}.main.sales").fetchone() == (
            2,
        )

        await k.delete_cell(DeleteCellCommand(cell_id=CellId_t("attached")))

        assert k.graph.cells["table"].run_result_status == "exception"
        assert duckdb.sql(
            f"SELECT * FROM memory.{alias}.main.sales"
        ).fetchone() == (1,)
        await k.delete_cell(DeleteCellCommand(cell_id=CellId_t("table")))
        assert duckdb.sql(
            f"SELECT * FROM memory.{alias}.main.sales"
        ).fetchone() == (1,)
    finally:
        duckdb.execute(f"DETACH DATABASE IF EXISTS {alias}")
        duckdb.execute(f"DROP SCHEMA IF EXISTS memory.{alias} CASCADE")


@pytest.mark.parametrize("alias", ["runner_partial_sql", "Runner_Partial_SQL"])
async def test_failed_multistatement_cleanup_removes_only_new_memory_tables(
    k: Kernel, exec_req: ExecReqProvider, alias: str
) -> None:
    import duckdb

    require_nested_schemas()
    try:
        duckdb.execute(
            f"CREATE SCHEMA memory.{alias}; CREATE SCHEMA memory.{alias}.main; "
            f"CREATE TABLE memory.{alias}.main.sales AS SELECT 1 AS amount"
        )
        sql = (
            f"CREATE TABLE memory.{alias}.main.created_here AS SELECT 2 AS amount; "
            f"CREATE TABLE memory.{alias}.main.sales AS SELECT 3 AS amount"
        )
        await k.run(
            [
                exec_req.get("import marimo as mo"),
                exec_req.get_with_id("table", f"mo.sql({sql!r})"),
            ]
        )
        assert k.graph.cells["table"].run_result_status == "exception"
        assert duckdb.sql(
            f"SELECT * FROM memory.{alias}.main.created_here"
        ).fetchone() == (2,)
        assert duckdb.sql(
            f"SELECT * FROM memory.{alias}.main.sales"
        ).fetchone() == (1,)

        await k.delete_cell(DeleteCellCommand(cell_id=CellId_t("table")))

        assert duckdb.sql(
            f"SELECT * FROM memory.{alias}.main.sales"
        ).fetchone() == (1,)
        with pytest.raises(duckdb.CatalogException):
            duckdb.sql(f"SELECT * FROM memory.{alias}.main.created_here")
    finally:
        duckdb.execute(f"DROP SCHEMA IF EXISTS memory.{alias} CASCADE")


async def test_failed_attach_does_not_detach_preexisting_catalog(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    import duckdb

    alias = "runner_existing_catalog"
    try:
        duckdb.execute(
            f"ATTACH ':memory:' AS {alias}; "
            f"CREATE TABLE {alias}.main.sales AS SELECT 1 AS amount"
        )
        await k.run(
            [
                exec_req.get("import marimo as mo"),
                exec_req.get_with_id(
                    "attached", f"mo.sql(\"ATTACH ':memory:' AS {alias}\")"
                ),
            ]
        )
        assert k.graph.cells["attached"].run_result_status == "exception"

        await k.delete_cell(DeleteCellCommand(cell_id=CellId_t("attached")))

        assert duckdb.sql(f"SELECT * FROM {alias}.main.sales").fetchone() == (
            1,
        )
    finally:
        duckdb.execute(f"DETACH DATABASE IF EXISTS {alias}")


@pytest.mark.parametrize(
    ("create", "expected_amount", "expected_status"),
    [
        ("CREATE TABLE", 1, "exception"),
        ("CREATE TABLE IF NOT EXISTS", 1, "success"),
        ("CREATE OR REPLACE TABLE", 2, "success"),
    ],
)
async def test_preexisting_memory_table_survives_cell_removal(
    k: Kernel,
    exec_req: ExecReqProvider,
    create: str,
    expected_amount: int,
    expected_status: str,
) -> None:
    import duckdb

    table = "runner_preexisting_memory_table"
    try:
        duckdb.execute(f"CREATE TABLE {table} AS SELECT 1 AS amount")
        await k.run(
            [
                exec_req.get("import duckdb"),
                exec_req.get_with_id(
                    "table",
                    f'duckdb.sql("{create} {table} AS SELECT 2 AS amount")',
                ),
            ]
        )
        assert k.graph.cells["table"].run_result_status == expected_status

        await k.delete_cell(DeleteCellCommand(cell_id=CellId_t("table")))

        assert duckdb.sql(f"SELECT * FROM {table}").fetchone() == (
            expected_amount,
        )
    finally:
        duckdb.execute(f"DROP TABLE IF EXISTS {table}")


async def test_deleting_errored_attach_invalidates_rebound_memory_reader(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    import duckdb

    alias = "runner_errored_catalog"
    try:
        duckdb.execute(f"CREATE SCHEMA memory.{alias}")
        await k.run([exec_req.get(f"import duckdb\ncalls = []\n{alias} = 1")])
        create = f"CREATE TABLE {alias}.sales AS SELECT 7 AS amount"
        query = f"SELECT * FROM memory.{alias}.sales"
        await k.run(
            [exec_req.get_with_id("source", f"duckdb.sql({create!r})")]
        )
        await k.run(
            [
                exec_req.get_with_id(
                    "reader",
                    f"calls.append(1)\nrows = duckdb.sql({query!r}).fetchall()",
                )
            ]
        )
        attach = f"ATTACH ':memory:' AS {alias}"
        await k.run(
            [exec_req.get_with_id("attach", f"duckdb.sql({attach!r})")]
        )
        assert CellId_t("attach") in k.errors
        assert CellId_t("source") not in k.graph.parents[CellId_t("reader")]
        calls_before_deletion = len(k.globals["calls"])

        await k.delete_cell(DeleteCellCommand(cell_id=CellId_t("attach")))

        assert not k.errors
        assert CellId_t("source") in k.graph.parents[CellId_t("reader")]
        assert len(k.globals["calls"]) == calls_before_deletion + 1
        assert k.globals["rows"] == [(7,)]
    finally:
        duckdb.execute(f"DETACH DATABASE IF EXISTS {alias}")
        duckdb.execute(f"DROP SCHEMA IF EXISTS memory.{alias} CASCADE")
