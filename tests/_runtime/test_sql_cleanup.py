# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import patch

import pytest

from marimo._ast.sql_visitor import SQLRef
from marimo._ast.visitor import VariableData
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.sql_cleanup import (
    SQLCleanupState,
    capture_sql_cleanup_state,
)
from marimo._sql.sql_quoting import quote_qualified_name


def test_python_definitions_do_not_inspect_sql_catalogs() -> None:
    with patch(
        "marimo._runtime.sql_cleanup._get_attached_catalogs"
    ) as catalogs:
        assert (
            capture_sql_cleanup_state({"value": [VariableData()]}, frozenset())
            is None
        )
    catalogs.assert_not_called()


@pytest.mark.skipif(
    not DependencyManager.duckdb.has(), reason="DuckDB required"
)
def test_failed_inspection_protects_all_cleanup_targets() -> None:
    path = ["finance.reports", 'a"b']
    variable = VariableData("table", sql_ref=SQLRef.from_parts(path))
    with (
        patch(
            "marimo._runtime.sql_cleanup._get_attached_catalogs",
            return_value=frozenset({"memory", "attached"}),
        ),
        patch(
            "marimo._sql.engines.duckdb.DuckDBEngine.get_tables_in_schema",
            side_effect=RuntimeError("metadata unavailable"),
        ),
    ):
        state = capture_sql_cleanup_state(
            {
                path[-1]: [variable],
                "attached": [VariableData("catalog")],
            },
            frozenset({"declared"}),
        )
    assert state is not None
    assert state == SQLCleanupState(
        catalogs=frozenset({"memory", "attached", "declared"}),
        protected_relations=frozenset({("memory", *path)}),
        protected_catalogs=frozenset({"attached"}),
    )
    with patch("duckdb.execute") as execute:
        state.delete_definition(path[-1], variable)
        state.delete_definition("attached", VariableData("catalog"))
    execute.assert_not_called()


@pytest.mark.skipif(
    not DependencyManager.duckdb.has(), reason="DuckDB required"
)
def test_existing_unbound_view_is_protected_without_querying_it() -> None:
    import duckdb

    table = "runtime_cleanup_view_source"
    view = "runtime_cleanup_unbound_view"
    qualified = quote_qualified_name("memory", "main", view)
    try:
        duckdb.execute(f"CREATE TABLE {table} AS SELECT 1 AS value")
        duckdb.execute(f"CREATE VIEW {qualified} AS SELECT * FROM {table}")
        duckdb.execute(f"DROP TABLE {table}")
        variable = VariableData("view", sql_ref=SQLRef(view))
        state = capture_sql_cleanup_state({view: [variable]}, frozenset())
        assert state is not None
        assert ("memory", "main", view) in state.protected_relations

        state.delete_definition(view, variable)

        assert duckdb.execute(
            "SELECT count(*) FROM duckdb_views() WHERE view_name = ?",
            [view],
        ).fetchone() == (1,)
    finally:
        duckdb.execute(f"DROP VIEW IF EXISTS {qualified}")
        duckdb.execute(f"DROP TABLE IF EXISTS {table}")
