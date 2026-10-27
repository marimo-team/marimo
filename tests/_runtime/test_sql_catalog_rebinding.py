# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.commands import DeleteCellCommand
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
