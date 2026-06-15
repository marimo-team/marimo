# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "duckdb",
#     "ibis-framework[duckdb]",
#     "marimo",
#     "pyarrow",
#     "pyiceberg[sql-sqlite]",
#     "sqlalchemy",
# ]
# ///

# Copyright 2026 Marimo. All rights reserved.
#
# Smoke test for SQL catalog expansion across local/no-server engines.

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="medium")


@app.cell
def _():
    from datetime import date
    from pathlib import Path
    from textwrap import dedent
    import sqlite3
    import tempfile

    import duckdb
    import ibis
    import marimo as mo
    import pyarrow as pa
    from pyiceberg.catalog import load_catalog
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    return (
        Path,
        StaticPool,
        create_engine,
        date,
        dedent,
        duckdb,
        ibis,
        load_catalog,
        mo,
        pa,
        sqlite3,
        tempfile,
    )


@app.cell(hide_code=True)
def _(dedent, mo):
    mo.md(
        dedent(
            """
            # SQL Catalog Children Smoke Test

            This notebook creates local in-memory or temporary databases with
            nested schemas, attached catalogs/databases, views, root-level
            tables, and PyIceberg namespaces.

            ### Manual test steps

            1. Open the data sources panel after the notebook finishes running.
            2. Expand every connection created below: `duckdb_conn`,
               `sqlite_conn`, `sqlalchemy_engine`, `ibis_conn`, and
               `iceberg_catalog`.
            3. Verify each expansion loads immediate children once and shows
               tables directly under engines/namespaces that expose root-level
               tables without an empty schema wrapper.
            """
        )
    )
    return


@app.cell
def _(Path, tempfile):
    catalog_smoke_tmp = tempfile.TemporaryDirectory(prefix="marimo-catalog-smoke-")
    catalog_smoke_root = Path(catalog_smoke_tmp.name)
    return (catalog_smoke_root,)


@app.cell(hide_code=True)
def _(catalog_smoke_root, dedent, mo):
    mo.md(
        dedent(
            f"""
            ## Temporary Workspace

            Temporary attached databases and warehouses live under:

            `{catalog_smoke_root}`
            """
        )
    )
    return


@app.cell(hide_code=True)
def _(dedent, mo):
    mo.md(
        dedent(
            """
            ## 1. DuckDB

            Creates a DuckDB in-memory connection with:

            - `memory.main.root_events`
            - `memory.retail.orders`
            - `memory.retail.high_value_orders` view
            - `memory.operations.inventory`
            - attached catalog `duck_lake.bronze.events`
            - attached catalog `duck_lake.silver.customer_rollups`
            """
        )
    )
    return


@app.cell
def _(catalog_smoke_root, duckdb):
    duckdb_conn = duckdb.connect(":memory:")
    _duck_lake_path = catalog_smoke_root / "duck_lake.duckdb"
    _duck_lake_sql_path = _duck_lake_path.as_posix().replace("'", "''")

    duckdb_conn.execute("CREATE SCHEMA retail")
    duckdb_conn.execute("CREATE SCHEMA operations")
    duckdb_conn.execute(
        """
        CREATE TABLE root_events (
            event_id INTEGER,
            event_name VARCHAR,
            payload STRUCT(region VARCHAR, amount DOUBLE)
        )
        """
    )
    duckdb_conn.execute(
        """
        INSERT INTO root_events VALUES
            (1, 'opened', {'region': 'us', 'amount': 10.5}),
            (2, 'clicked', {'region': 'eu', 'amount': 20.0})
        """
    )
    duckdb_conn.execute(
        """
        CREATE TABLE retail.orders (
            order_id INTEGER,
            customer VARCHAR,
            amount DOUBLE,
            tags VARCHAR[]
        )
        """
    )
    duckdb_conn.execute(
        """
        INSERT INTO retail.orders VALUES
            (101, 'Ada', 125.50, ['new', 'priority']),
            (102, 'Grace', 83.00, ['returning'])
        """
    )
    duckdb_conn.execute(
        """
        CREATE VIEW retail.high_value_orders AS
        SELECT * FROM retail.orders WHERE amount > 100
        """
    )
    duckdb_conn.execute(
        """
        CREATE TABLE operations.inventory (
            sku VARCHAR,
            warehouse VARCHAR,
            quantity INTEGER
        )
        """
    )
    duckdb_conn.execute(
        """
        INSERT INTO operations.inventory VALUES
            ('sku-1', 'west', 10),
            ('sku-2', 'east', 25)
        """
    )
    duckdb_conn.execute(f"ATTACH '{_duck_lake_sql_path}' AS duck_lake")
    duckdb_conn.execute("CREATE SCHEMA duck_lake.bronze")
    duckdb_conn.execute("CREATE SCHEMA duck_lake.silver")
    duckdb_conn.execute(
        """
        CREATE TABLE duck_lake.bronze.events (
            event_id INTEGER,
            source VARCHAR,
            received_at TIMESTAMP
        )
        """
    )
    duckdb_conn.execute(
        """
        INSERT INTO duck_lake.bronze.events VALUES
            (1, 'sensor-a', CURRENT_TIMESTAMP),
            (2, 'sensor-b', CURRENT_TIMESTAMP)
        """
    )
    duckdb_conn.execute(
        """
        CREATE TABLE duck_lake.silver.customer_rollups (
            customer VARCHAR,
            total_amount DOUBLE
        )
        """
    )
    duckdb_conn.execute(
        """
        INSERT INTO duck_lake.silver.customer_rollups VALUES
            ('Ada', 125.50),
            ('Grace', 83.00)
        """
    )

    _duckdb_tables = duckdb_conn.execute("SHOW ALL TABLES").fetchall()
    assert any(
        _row[0] == "memory" and _row[1] == "retail" for _row in _duckdb_tables
    )
    assert any(
        _row[0] == "duck_lake" and _row[1] == "bronze" for _row in _duckdb_tables
    )
    return (duckdb_conn,)


@app.cell
def _(duckdb_conn, mo):
    _duckdb_preview = mo.sql(
        f"""
        -- Keep this as an f-string so SQL identifiers are not notebook deps: {""}
        SELECT 'duckdb' AS engine, COUNT(*) AS order_count
        FROM retail.orders
        """,
        engine=duckdb_conn,
    )
    _duckdb_preview
    return


@app.cell(hide_code=True)
def _(dedent, mo):
    mo.md(
        dedent(
            """
            ## 2. SQLite DB-API

            Creates a pure `sqlite3.Connection` with:

            - `main.raw_orders`
            - attached database `tenant_a.customer_profiles`
            - attached database `tenant_a.line_items`
            - attached database `tenant_b.audit_log`
            """
        )
    )
    return


@app.cell
def _(catalog_smoke_root, sqlite3):
    sqlite_conn = sqlite3.connect(":memory:")
    _tenant_a = catalog_smoke_root / "sqlite_tenant_a.db"
    _tenant_b = catalog_smoke_root / "sqlite_tenant_b.db"
    sqlite_conn.execute(f"ATTACH DATABASE '{_tenant_a}' AS tenant_a")
    sqlite_conn.execute(f"ATTACH DATABASE '{_tenant_b}' AS tenant_b")
    sqlite_conn.executescript(
        """
        CREATE TABLE main.raw_orders (
            order_id INTEGER PRIMARY KEY,
            customer TEXT,
            amount REAL
        );
        INSERT INTO main.raw_orders VALUES
            (1, 'Ada', 125.50),
            (2, 'Grace', 83.00);

        CREATE TABLE tenant_a.customer_profiles (
            customer_id INTEGER PRIMARY KEY,
            name TEXT,
            preferences TEXT
        );
        INSERT INTO tenant_a.customer_profiles VALUES
            (1, 'Ada', '{"tier": "gold"}'),
            (2, 'Grace', '{"tier": "silver"}');

        CREATE TABLE tenant_a.line_items (
            order_id INTEGER,
            sku TEXT,
            quantity INTEGER
        );
        INSERT INTO tenant_a.line_items VALUES
            (1, 'sku-1', 2),
            (2, 'sku-2', 1);

        CREATE TABLE tenant_b.audit_log (
            audit_id INTEGER PRIMARY KEY,
            action TEXT,
            actor TEXT
        );
        INSERT INTO tenant_b.audit_log VALUES
            (1, 'created', 'smoke-test'),
            (2, 'updated', 'smoke-test');
        """
    )
    sqlite_conn.commit()

    _sqlite_schemas = [
        _row[1] for _row in sqlite_conn.execute("PRAGMA database_list")
    ]
    assert {"main", "tenant_a", "tenant_b"}.issubset(_sqlite_schemas)
    return (sqlite_conn,)


@app.cell
def _(mo, raw_orders, sqlite_conn):
    _sqlite_preview = mo.sql(
        f"""
        -- Keep this as an f-string so SQL identifiers are not notebook deps: {""}
        SELECT 'sqlite3' AS engine, COUNT(*) AS raw_order_count
        FROM raw_orders
        """,
        engine=sqlite_conn,
    )
    _sqlite_preview
    return


@app.cell(hide_code=True)
def _(dedent, mo):
    mo.md(
        dedent(
            """
            ## 3. SQLAlchemy SQLite

            Creates a SQLAlchemy engine backed by one persistent in-memory
            SQLite connection, with attached temporary databases:

            - `main.warehouse_items`
            - `staging.incoming_shipments`
            - `archive.shipment_history`
            """
        )
    )
    return


@app.cell
def _(StaticPool, catalog_smoke_root, create_engine):
    sqlalchemy_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _staging = catalog_smoke_root / "sqlalchemy_staging.db"
    _archive = catalog_smoke_root / "sqlalchemy_archive.db"
    with sqlalchemy_engine.begin() as _conn:
        _conn.exec_driver_sql(f"ATTACH DATABASE '{_staging}' AS staging")
        _conn.exec_driver_sql(f"ATTACH DATABASE '{_archive}' AS archive")
        _conn.exec_driver_sql(
            """
            CREATE TABLE warehouse_items (
                sku TEXT PRIMARY KEY,
                name TEXT,
                quantity INTEGER
            )
            """
        )
        _conn.exec_driver_sql(
            """
            INSERT INTO warehouse_items VALUES
                ('sku-1', 'Notebook', 20),
                ('sku-2', 'Pen', 200)
            """
        )
        _conn.exec_driver_sql(
            """
            CREATE TABLE staging.incoming_shipments (
                shipment_id INTEGER PRIMARY KEY,
                sku TEXT,
                expected_quantity INTEGER
            )
            """
        )
        _conn.exec_driver_sql(
            """
            INSERT INTO staging.incoming_shipments VALUES
                (10, 'sku-1', 5),
                (11, 'sku-3', 50)
            """
        )
        _conn.exec_driver_sql(
            """
            CREATE TABLE archive.shipment_history (
                shipment_id INTEGER PRIMARY KEY,
                sku TEXT,
                received_quantity INTEGER
            )
            """
        )
        _conn.exec_driver_sql(
            """
            INSERT INTO archive.shipment_history VALUES
                (1, 'sku-1', 10),
                (2, 'sku-2', 25)
            """
        )

    with sqlalchemy_engine.connect() as _conn:
        _attached = [
            _row[1] for _row in _conn.exec_driver_sql("PRAGMA database_list")
        ]
    assert {"main", "staging", "archive"}.issubset(_attached)
    return (sqlalchemy_engine,)


@app.cell
def _(mo, sqlalchemy_engine, warehouse_items):
    _sqlalchemy_preview = mo.sql(
        f"""
        -- Keep this as an f-string so SQL identifiers are not notebook deps: {""}
        SELECT 'sqlalchemy' AS engine, COUNT(*) AS item_count
        FROM warehouse_items
        """,
        engine=sqlalchemy_engine,
    )
    _sqlalchemy_preview
    return


@app.cell(hide_code=True)
def _(dedent, mo):
    mo.md(
        dedent(
            """
            ## 4. Ibis DuckDB Backend

            Creates an Ibis DuckDB backend with:

            - default `main.ibis_root_metrics`
            - `analytics.ibis_orders`
            - attached catalog `ibis_lake.mart.customer_features`
            """
        )
    )
    return


@app.cell
def _(catalog_smoke_root, ibis, pa):
    ibis.options.interactive = True
    ibis_conn = ibis.duckdb.connect()
    _ibis_lake = catalog_smoke_root / "ibis_lake.duckdb"
    _ibis_lake_sql_path = _ibis_lake.as_posix().replace("'", "''")

    ibis_conn.raw_sql("CREATE SCHEMA analytics")
    ibis_conn.raw_sql(f"ATTACH '{_ibis_lake_sql_path}' AS ibis_lake")
    ibis_conn.raw_sql("CREATE SCHEMA ibis_lake.mart")

    _root_metrics = pa.table(
        {
            "metric": ["latency_ms", "throughput"],
            "value": [42.5, 900.0],
        }
    )
    _orders = pa.table(
        {
            "order_id": [1, 2],
            "customer": ["Ada", "Grace"],
            "amount": [125.5, 83.0],
        }
    )
    _features = pa.table(
        {
            "customer": ["Ada", "Grace"],
            "segment": ["enterprise", "startup"],
            "score": [0.98, 0.87],
        }
    )

    ibis_conn.create_table("ibis_root_metrics", obj=_root_metrics, overwrite=True)
    ibis_conn.create_table(
        "ibis_orders", obj=_orders, database="analytics", overwrite=True
    )
    ibis_conn.create_table(
        "customer_features",
        obj=_features,
        database="ibis_lake.mart",
        overwrite=True,
    )

    assert "ibis_root_metrics" in ibis_conn.list_tables(
        database=("memory", "main")
    )
    assert "ibis_orders" in ibis_conn.list_tables(database=("memory", "analytics"))
    assert "customer_features" in ibis_conn.list_tables(
        database=("ibis_lake", "mart")
    )
    return (ibis_conn,)


@app.cell
def _(ibis_conn, mo):
    _ibis_preview = mo.sql(
        f"""
        -- Keep this as an f-string so SQL identifiers are not notebook deps: {""}
        SELECT 'ibis' AS engine, COUNT(*) AS order_count
        FROM analytics.ibis_orders
        """,
        engine=ibis_conn,
    )
    _ibis_preview
    return


@app.cell(hide_code=True)
def _(dedent, mo):
    mo.md(
        dedent(
            """
            ## 5. PyIceberg SQL Catalog

            Creates a temporary SQLite-backed Iceberg catalog and local file
            warehouse with nested namespaces:

            - `top.root_table`
            - `top.nested.orders`
            - `top.nested.deep.line_items`
            - `top.reporting.daily_rollups`
            """
        )
    )
    return


@app.cell
def _(catalog_smoke_root, date, load_catalog, pa):
    _warehouse_path = catalog_smoke_root / "iceberg_warehouse"
    _warehouse_path.mkdir(parents=True, exist_ok=True)
    _catalog_db = catalog_smoke_root / "pyiceberg_catalog.db"
    iceberg_catalog = load_catalog(
        "catalog_smoke",
        **{
            "type": "sql",
            "uri": f"sqlite:///{_catalog_db}",
            "warehouse": f"file://{_warehouse_path}",
        },
    )

    for _namespace in [
        "top",
        "top.nested",
        "top.nested.deep",
        "top.reporting",
    ]:
        iceberg_catalog.create_namespace_if_not_exists(_namespace)

    _root_schema = pa.schema([("id", pa.int32()), ("label", pa.string())])
    _order_schema = pa.schema(
        [
            ("order_id", pa.int32()),
            ("customer", pa.string()),
            ("amount", pa.float64()),
        ]
    )
    _line_item_schema = pa.schema(
        [
            ("order_id", pa.int32()),
            ("sku", pa.string()),
            ("quantity", pa.int32()),
        ]
    )
    _rollup_schema = pa.schema(
        [
            ("report_date", pa.date32()),
            ("order_count", pa.int32()),
            ("gross_sales", pa.float64()),
        ]
    )

    _root_table = iceberg_catalog.create_table_if_not_exists(
        "top.root_table", schema=_root_schema
    )
    _orders_table = iceberg_catalog.create_table_if_not_exists(
        "top.nested.orders", schema=_order_schema
    )
    _line_items_table = iceberg_catalog.create_table_if_not_exists(
        "top.nested.deep.line_items", schema=_line_item_schema
    )
    _rollups_table = iceberg_catalog.create_table_if_not_exists(
        "top.reporting.daily_rollups", schema=_rollup_schema
    )

    _root_table.overwrite(
        pa.table(
            {
                "id": pa.array([1, 2], type=pa.int32()),
                "label": ["root-a", "root-b"],
            }
        )
    )
    _orders_table.overwrite(
        pa.table(
            {
                "order_id": pa.array([1, 2], type=pa.int32()),
                "customer": ["Ada", "Grace"],
                "amount": [125.5, 83.0],
            }
        )
    )
    _line_items_table.overwrite(
        pa.table(
            {
                "order_id": pa.array([1, 1, 2], type=pa.int32()),
                "sku": ["sku-1", "sku-2", "sku-3"],
                "quantity": pa.array([2, 1, 4], type=pa.int32()),
            }
        )
    )
    _rollups_table.overwrite(
        pa.table(
            {
                "report_date": pa.array([date(2026, 6, 13)], type=pa.date32()),
                "order_count": pa.array([2], type=pa.int32()),
                "gross_sales": [208.5],
            }
        )
    )

    assert ("top", "nested") in iceberg_catalog.list_namespaces("top")
    assert ("top", "nested", "deep") in iceberg_catalog.list_namespaces(
        "top.nested"
    )
    assert ("top", "nested", "orders") in iceberg_catalog.list_tables("top.nested")
    return (iceberg_catalog,)


@app.cell
def _(iceberg_catalog, mo):
    _iceberg_orders = (
        iceberg_catalog.load_table("top.nested.orders").scan().to_arrow()
    )
    assert _iceberg_orders.num_rows == 2
    mo.md("**PyIceberg table load:** PASS")
    return


@app.cell(hide_code=True)
def _(dedent, mo):
    mo.md(
        dedent(
            """
            ## Catalog Panel Checklist

            Use the data sources panel to verify these expansion paths:

            - `duckdb_conn`: `memory -> retail -> orders`,
              `memory -> retail -> high_value_orders`,
              `duck_lake -> bronze -> events`.
            - `sqlite_conn`: `main -> raw_orders`,
              `tenant_a -> customer_profiles`, `tenant_b -> audit_log`.
            - `sqlalchemy_engine`: `main -> warehouse_items`,
              `staging -> incoming_shipments`,
              `archive -> shipment_history`.
            - `ibis_conn`: `memory -> main -> ibis_root_metrics`,
              `memory -> analytics -> ibis_orders`,
              `ibis_lake -> mart -> customer_features`.
            - `iceberg_catalog`: `top -> root_table`,
              `top -> nested -> orders`,
              `top -> nested -> deep -> line_items`,
              `top -> reporting -> daily_rollups`.
            """
        )
    )
    return


if __name__ == "__main__":
    app.run()
