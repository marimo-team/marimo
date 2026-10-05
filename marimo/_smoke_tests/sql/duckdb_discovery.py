# Copyright 2026 Marimo. All rights reserved.
# Run from this checkout so the notebook exercises the PR implementation:
# uv run --with duckdb marimo edit marimo/_smoke_tests/sql/duckdb_discovery.py

import marimo

__generated_with = "0.25.0"
app = marimo.App(width="medium")


@app.cell
def _():
    from itertools import product
    from typing import Any

    import duckdb
    import msgspec

    import marimo as mo
    from marimo._sql.engines.duckdb import DuckDBEngine
    from marimo._types.ids import VariableName

    return Any, DuckDBEngine, VariableName, duckdb, mo, msgspec, product


@app.cell(hide_code=True)
def _(duckdb, mo):
    mo.md(f"""
    # DuckDB discovery smoke test

    Verifies issue **#11003** and PR **#11007** against this checkout.
    Uses small in-memory catalogs; no downloads, credentials, or extensions.

    **DuckDB:** `{duckdb.__version__}`

    **marimo loaded from:** `{mo.__file__}`

    The checks below inspect real metadata results and record the SQL sent
    through the engine. They verify query counts, not remote Iceberg latency.
    One check deliberately simulates an unavailable column-metadata query.
    """)
    return


@app.cell
def _(duckdb):
    def create_smoke_connection() -> duckdb.DuckDBPyConnection:
        connection = duckdb.connect()
        connection.execute("""
            CREATE SCHEMA retail;
            CREATE TABLE retail.orders AS
                SELECT i AS order_id, i * 10 AS amount FROM range(1, 101) t(i);
            CREATE VIEW retail.large_orders AS
                SELECT * FROM retail.orders WHERE amount >= 500;
            CREATE SCHEMA empty_schema;
            CREATE TEMP TABLE scratch AS SELECT 1 AS id;
            ATTACH ':memory:' AS warehouse;
            CREATE SCHEMA warehouse.analytics;
            CREATE TABLE warehouse.analytics.orders AS SELECT 42 AS warehouse_id;
            ATTACH ':memory:' AS "odd""catalog";
            CREATE SCHEMA "odd""catalog"."sales.region";
            CREATE TABLE "odd""catalog"."sales.region"."order""details" (id INTEGER);
        """)
        return connection

    smoke_connection = create_smoke_connection()
    return create_smoke_connection, smoke_connection


@app.cell
def _(Any, DuckDBEngine, VariableName):
    class ObservedDuckDBEngine(DuckDBEngine):
        """Record this engine's queries without patching notebook-wide state."""

        def __init__(self, connection):
            super().__init__(connection, VariableName("smoke_connection"))
            self.queries: list[dict[str, Any]] = []
            self.fail_columns = False

        def _query_catalog(
            self, query: str, params: list[Any] | None = None
        ) -> list[Any]:
            self.queries.append({"sql": query, "parameters": repr(params)})
            if self.fail_columns and "duckdb_columns()" in query:
                raise RuntimeError("Simulated column catalog failure")
            return super()._query_catalog(query, params)

    return (ObservedDuckDBEngine,)


@app.cell(hide_code=True)
def _(mo):
    schema_flag = mo.ui.dropdown(
        {"Disabled": False, "Enabled": True, "Auto": "auto"},
        value="Disabled",
        label="Schemas",
    )
    table_flag = mo.ui.dropdown(
        {"Disabled": False, "Enabled": True, "Auto": "auto"},
        value="Enabled",
        label="Tables",
    )
    column_flag = mo.ui.dropdown(
        {"Disabled": False, "Enabled": True, "Auto": "auto"},
        value="Enabled",
        label="Columns",
    )
    mo.vstack(
        [
            mo.md("""## Explore discovery depth

        These controls pass flags directly to the engine. They do not change
        your marimo settings. Disabled schemas prevent table and column work;
        disabled tables prevent column work. `Auto` retains DuckDB's existing
        cheap-dialect policy and resolves to enabled.
        """),
            mo.hstack([schema_flag, table_flag, column_flag]),
        ]
    )
    return column_flag, schema_flag, table_flag


@app.cell
def _(
    ObservedDuckDBEngine,
    column_flag,
    schema_flag,
    smoke_connection,
    table_flag,
):
    observed_engine = ObservedDuckDBEngine(smoke_connection)
    discovered_catalogs = observed_engine.get_databases(
        include_schemas=schema_flag.value,
        include_tables=table_flag.value,
        include_table_details=column_flag.value,
    )
    return discovered_catalogs, observed_engine


@app.cell(hide_code=True)
def _(discovered_catalogs, mo, msgspec, observed_engine):
    mo.vstack(
        [
            mo.md(f"**Metadata queries: {len(observed_engine.queries)}**"),
            mo.ui.table(observed_engine.queries, selection=None),
            mo.accordion(
                {
                    "Returned catalog metadata": mo.json(
                        msgspec.to_builtins(discovered_catalogs)
                    )
                }
            ),
        ]
    )
    return


@app.cell
def _(ObservedDuckDBEngine, create_smoke_connection, product):
    check_results = []

    def record_check(name, check) -> None:
        try:
            detail = check()
        except Exception as error:
            check_results.append(
                {"check": name, "status": "FAIL", "detail": repr(error)}
            )
        else:
            check_results.append(
                {"check": name, "status": "PASS", "detail": detail}
            )

    def verify_flags(schemas, tables, columns) -> str:
        with create_smoke_connection() as connection:
            engine = ObservedDuckDBEngine(connection)
            catalogs = engine.get_databases(
                include_schemas=schemas,
                include_tables=tables,
                include_table_details=columns,
            )
            schemas_enabled = schemas is not False
            tables_enabled = schemas_enabled and tables is not False
            columns_enabled = tables_enabled and columns is not False
            queries = [entry["sql"] for entry in engine.queries]
            assert {catalog.name for catalog in catalogs} == {
                "memory",
                "temp",
                "warehouse",
                'odd"catalog',
            }
            assert sum(
                "duckdb_schemas()" in query for query in queries
            ) == int(schemas_enabled)
            assert sum(
                "duckdb_columns()" in query for query in queries
            ) == int(columns_enabled)
            assert (
                any("information_schema.tables" in query for query in queries)
                == tables_enabled
            )
            for catalog in catalogs:
                assert catalog.schemas_resolved == schemas_enabled
                if not schemas_enabled:
                    assert catalog.schemas == []
                for schema in catalog.schemas:
                    assert schema.tables_resolved == tables_enabled
                    if not tables_enabled:
                        assert schema.tables == []
                    for table in schema.tables:
                        assert bool(table.columns) == columns_enabled
                        assert (
                            table.num_columns is not None
                        ) == columns_enabled
            return f"{len(queries)} queries; schema scans={int(schemas_enabled)}, column scans={int(columns_enabled)}"

    for _schemas, _tables, _columns in product(
        [False, True, "auto"], repeat=3
    ):
        record_check(
            f"Flags: schemas={_schemas}, tables={_tables}, columns={_columns}",
            lambda s=_schemas, t=_tables, c=_columns: verify_flags(s, t, c),
        )

    def verify_deferred_loading() -> str:
        with create_smoke_connection() as connection:
            engine = ObservedDuckDBEngine(connection)
            engine.get_databases(
                include_schemas=False,
                include_tables=False,
                include_table_details=False,
            )
            schemas = engine.get_schemas(
                database="memory",
                include_tables=False,
                include_table_details=False,
            )
            assert "empty_schema" in {schema.name for schema in schemas}
            assert all(not schema.tables_resolved for schema in schemas)
            tables = engine.get_tables_in_schema(
                database="memory", schema="retail", include_table_details=False
            )
            assert [(table.name, table.type) for table in tables] == [
                ("large_orders", "view"),
                ("orders", "table"),
            ]
            assert all(table.columns == [] for table in tables)
            view = engine.get_table_details(
                database_name="memory",
                schema_name="retail",
                table_name="large_orders",
            )
            assert view is not None
            assert view.type == "view"
            assert [column.name for column in view.columns] == [
                "order_id",
                "amount",
            ]
            quoted = engine.get_table_details(
                database_name='odd"catalog',
                schema_name="sales.region",
                table_name='order"details',
            )
            assert quoted is not None
            assert [column.name for column in quoted.columns] == ["id"]
            temporary = engine.get_tables_in_schema(
                database="temp", schema="main", include_table_details=True
            )
            assert [table.name for table in temporary] == ["scratch"]
            assert [column.name for column in temporary[0].columns] == ["id"]
            return "Empty schemas, views, quoted identifiers, and temporary tables load correctly"

    record_check(
        "Deferred expansion and object types", verify_deferred_loading
    )

    def verify_metadata_failure() -> str:
        with create_smoke_connection() as connection:
            engine = ObservedDuckDBEngine(connection)
            engine.fail_columns = True
            tables = engine.get_tables_in_schema(
                database="memory", schema="retail", include_table_details=True
            )
            assert [(table.name, table.type) for table in tables] == [
                ("large_orders", "view"),
                ("orders", "table"),
            ]
            assert all(
                table.columns == [] and table.num_columns is None
                for table in tables
            )
            return "Both objects remain visible after the simulated column failure"

    record_check(
        "Column metadata failure preserves tables", verify_metadata_failure
    )
    return (check_results,)


@app.cell(hide_code=True)
def _(check_results, mo):
    _failures = [
        result for result in check_results if result["status"] == "FAIL"
    ]
    mo.vstack(
        [
            mo.md(
                f"## Automated checks: {len(check_results) - len(_failures)}/{len(check_results)} passed"
            ),
            mo.ui.table(check_results, selection=None),
        ]
    )
    return


@app.cell
def _(check_results):
    assert all(result["status"] == "PASS" for result in check_results), [
        result for result in check_results if result["status"] == "FAIL"
    ]
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Manual datasource-panel check

    1. Open the **Data Sources** panel and find `smoke_connection`.
    2. Expand `memory` → `retail`. `large_orders` should be a view and
       `orders` a table. Expand each to load `order_id` and `amount`.
    3. Expand `temp` → `main` → `scratch`, and the quoted catalog and table.
    4. Disable schema, table, and column auto-discovery in datasource settings,
       refresh the connection, and repeat the expansions. Restore your settings
       afterward. The controls above affect only the recorded engine calls.

    **Expected warning:** the failure check intentionally logs
    `Simulated column catalog failure`. Its result should still be **PASS**.

    This notebook cannot establish real Iceberg network performance. A remote
    REST catalog with credentials is needed for that measurement; a public CSV
    would exercise data reads rather than catalog discovery.
    """)
    return


if __name__ == "__main__":
    app.run()
