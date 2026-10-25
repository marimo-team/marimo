# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._ast.sql_visitor import SQLRef
from marimo._ast.visitor import VariableData
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.commands import DeleteCellCommand, UpdateCellConfigCommand
from marimo._runtime.dataflow.definitions import DefinitionRegistry
from marimo._runtime.runtime import Kernel
from marimo._types.ids import CellId_t
from tests.conftest import ExecReqProvider


@pytest.mark.parametrize("python_binding", [False, True])
def test_catalog_definition_survives_same_leaf_relation(
    python_binding: bool,
) -> None:
    registry = DefinitionRegistry()
    cell_id = CellId_t("owner")
    variables = [
        VariableData("catalog"),
        VariableData("table", sql_ref=SQLRef("shared", schema="shared")),
    ]
    if python_binding:
        variables.append(VariableData())
    registry.register_definition(cell_id, "shared", variables)
    assert registry.sql_catalogs == frozenset({"shared"})
    assert registry.typed_definitions == {
        ("shared", kind): {cell_id}
        for kind in [
            "catalog",
            "table",
            *(["variable"] if python_binding else []),
        ]
    }

    registry.unregister_definitions(cell_id, {"shared": variables})

    assert (
        registry.definitions,
        registry.typed_definitions,
        registry.definition_conflicts,
        registry.conflict_names,
    ) == ({}, {}, {}, {})


requires_sql = pytest.mark.skipif(
    not DependencyManager.duckdb.has() or not DependencyManager.sqlglot.has(),
    reason="SQL dependencies required",
)


@requires_sql
async def test_skipped_attach_does_not_prevent_memory_relation_cleanup(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    import duckdb

    alias = "cleanup_skipped_catalog"
    try:
        duckdb.execute(f"CREATE SCHEMA memory.{alias}")
        await k.run([exec_req.get("import duckdb")])
        await k.run(
            [
                exec_req.get_with_id(
                    "attach",
                    f"if False:\n    duckdb.sql(\"ATTACH ':memory:' AS {alias}\")",
                )
            ]
        )
        assert alias in k.graph.definition_registry.sql_catalogs
        await k.run(
            [
                exec_req.get_with_id(
                    "table",
                    f'duckdb.sql("CREATE TABLE {alias}.sales AS SELECT 1 AS marker")',
                )
            ]
        )
        assert not k.errors
        assert duckdb.sql(
            f"SELECT * FROM memory.{alias}.sales"
        ).fetchone() == (1,)

        await k.delete_cell(DeleteCellCommand(cell_id=CellId_t("table")))

        assert duckdb.sql(
            "SELECT count(*) FROM duckdb_tables() WHERE database_name = 'memory' "
            "AND schema_name = ? AND table_name = 'sales'",
            params=[alias],
        ).fetchone() == (0,)
    finally:
        duckdb.execute(f"DETACH DATABASE IF EXISTS {alias}")
        duckdb.execute(f"DROP SCHEMA IF EXISTS memory.{alias} CASCADE")


@requires_sql
async def test_cleanup_uses_catalog_binding_before_external_detach(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    import duckdb

    alias = "cleanup_historical_binding"
    try:
        await k.run([exec_req.get("import duckdb")])
        await k.run(
            [
                exec_req.get_with_id(
                    "attach", f"duckdb.sql(\"ATTACH ':memory:' AS {alias}\")"
                )
            ]
        )
        await k.run(
            [
                exec_req.get_with_id(
                    "table",
                    f'duckdb.sql("CREATE TABLE {alias}.sales AS SELECT 2 AS marker")',
                )
            ]
        )
        assert not k.errors
        await k.set_cell_config(
            UpdateCellConfigCommand(
                configs={CellId_t("table"): {"disabled": True}}
            )
        )
        duckdb.execute(f"CREATE SCHEMA memory.{alias}")
        duckdb.execute(
            f"CREATE TABLE memory.{alias}.sales AS SELECT 99 AS marker"
        )
        duckdb.execute(f"DETACH {alias}")

        await k.delete_cell(DeleteCellCommand(cell_id=CellId_t("table")))

        assert duckdb.sql(
            f"SELECT * FROM memory.{alias}.sales"
        ).fetchone() == (99,)
    finally:
        duckdb.execute(f"DETACH DATABASE IF EXISTS {alias}")
        duckdb.execute(f"DROP SCHEMA IF EXISTS memory.{alias} CASCADE")


@requires_sql
@pytest.mark.parametrize("kind", ["TABLE", "VIEW"])
async def test_never_executed_cell_does_not_own_existing_relation(
    k: Kernel, exec_req: ExecReqProvider, kind: str
) -> None:
    import duckdb

    name = "cleanup_never_executed"
    try:
        duckdb.execute(f"CREATE {kind} {name} AS SELECT 99 AS marker")
        await k.run([exec_req.get("import duckdb")])
        await k.set_cell_config(
            UpdateCellConfigCommand(
                configs={CellId_t("table"): {"disabled": True}}
            )
        )
        await k.run(
            [
                exec_req.get_with_id(
                    "table",
                    f'duckdb.sql("CREATE OR REPLACE {kind} {name} AS SELECT 2 AS marker")',
                )
            ]
        )
        assert k.graph.cells["table"].config.disabled
        assert CellId_t("table") not in k._sql_cleanup_states

        await k.delete_cell(DeleteCellCommand(cell_id=CellId_t("table")))

        assert duckdb.sql(f"SELECT * FROM {name}").fetchone() == (99,)
    finally:
        duckdb.execute(f"DROP {kind} IF EXISTS {name}")
