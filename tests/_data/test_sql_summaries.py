from __future__ import annotations

import datetime
from typing import Any

import pytest

from marimo._data.models import ColumnStats
from marimo._data.sql_summaries import get_column_type, get_sql_stats
from marimo._dependencies.dependencies import DependencyManager

HAS_DEPS = DependencyManager.duckdb.has()


@pytest.fixture
def setup_test_db():
    if not HAS_DEPS:
        pytest.skip("optional dependencies not installed")

    import duckdb

    # Create a test database and table
    duckdb.execute("""
        CREATE OR REPLACE TABLE test_table_3 (
            id INTEGER,
            name VARCHAR,
            age INTEGER,
            salary DECIMAL(10, 2),
            is_active BOOLEAN,
            birth_date DATE,
            time_col TIME,
            datetime_col DATETIME
        )
    """)

    # Insert some test data
    duckdb.execute("""
        INSERT INTO test_table_3 VALUES
        (1, 'Alice', 30, 50000.00, true, '1993-01-15', '12:30:00', '2024-01-01 12:30:00'),
        (2, 'Bob', 35, 60000.00, false, '1988-05-20', '13:45:00', '2024-02-02 13:45:00'),
        (3, 'Charlie', 28, 45000.00, true, '1995-11-30', '14:00:00', '2024-03-03 14:00:00'),
        (4, 'David', NULL, 55000.00, true, '1990-08-10', '15:15:00', '2024-04-04 15:15:00'),
        (5, 'Eve', 32, NULL, false, '1991-03-25', '16:30:00', '2024-05-05 16:30:00')
    """)

    yield duckdb

    duckdb.execute("DROP TABLE test_table_3")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_column_type(setup_test_db: Any):
    del setup_test_db

    assert get_column_type("test_table_3", "id") == "integer"
    assert get_column_type("test_table_3", "name") == "string"
    assert get_column_type("test_table_3", "salary") == "number"
    assert get_column_type("test_table_3", "is_active") == "boolean"
    assert get_column_type("test_table_3", "birth_date") == "date"


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_sql_summary_integer(setup_test_db: Any):
    del setup_test_db

    summary = get_sql_stats("test_table_3", "age", "integer")
    assert isinstance(summary, ColumnStats)
    assert summary.total == 5
    assert summary.unique == 4
    assert summary.nulls == 1
    assert summary.min == 28
    assert summary.max == 35
    assert summary.mean == 31.25  # (30 + 35 + 28 + 32) / 4


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_sql_summary_string(setup_test_db: Any):
    del setup_test_db

    summary = get_sql_stats("test_table_3", "name", "string")
    assert isinstance(summary, ColumnStats)
    assert summary.total == 5
    assert summary.unique == 5
    assert summary.nulls == 0


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_sql_summary_boolean(setup_test_db: Any):
    del setup_test_db

    summary = get_sql_stats("test_table_3", "is_active", "boolean")
    assert isinstance(summary, ColumnStats)
    assert summary.total == 5
    assert summary.unique == 2
    assert summary.nulls == 0
    assert summary.true == 3
    assert summary.false == 2


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_sql_summary_date(setup_test_db: Any):
    del setup_test_db

    summary = get_sql_stats("test_table_3", "birth_date", "date")
    assert isinstance(summary, ColumnStats)
    assert summary.total == 5
    assert summary.unique == 5
    assert summary.nulls == 0
    assert summary.min == datetime.date(1988, 5, 20)
    assert summary.max == datetime.date(1995, 11, 30)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_sql_summary_time(setup_test_db: Any):
    del setup_test_db

    summary = get_sql_stats("test_table_3", "time_col", "time")
    assert isinstance(summary, ColumnStats)
    assert summary.total == 5
    assert summary.unique == 5
    assert summary.nulls == 0
    assert summary.min == datetime.time(12, 30)
    assert summary.max == datetime.time(16, 30)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_sql_summary_datetime(setup_test_db: Any):
    del setup_test_db

    summary = get_sql_stats("test_table_3", "datetime_col", "datetime")
    assert isinstance(summary, ColumnStats)
    assert summary.total == 5
    assert summary.unique == 5
    assert summary.nulls == 0
    assert summary.min == datetime.datetime(2024, 1, 1, 12, 30)
    assert summary.max == datetime.datetime(2024, 5, 5, 16, 30)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_geometry_column_type_and_stats():
    import duckdb

    try:
        duckdb.execute("INSTALL spatial")
        duckdb.execute("LOAD spatial")
    except duckdb.Error as e:
        pytest.skip(f"duckdb spatial extension unavailable: {e}")

    duckdb.execute(
        "CREATE OR REPLACE TABLE geo_stats_table AS "
        "SELECT 1 AS id, ST_Point(1.0, 2.0) AS geom "
        "UNION ALL SELECT 2, NULL"
    )
    try:
        assert get_column_type("geo_stats_table", "geom") == "geometry"

        summary = get_sql_stats("geo_stats_table", "geom", "geometry")
        assert summary.total == 2
        assert summary.nulls == 1
        assert summary.unique is None
    finally:
        duckdb.execute("DROP TABLE geo_stats_table")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_nested_column_type() -> None:
    import duckdb

    from marimo._sql.utils import is_duckdb_v2

    if not is_duckdb_v2():
        pytest.skip("Nested schemas require DuckDB 2")
    try:
        duckdb.execute(
            "CREATE SCHEMA type_test; CREATE SCHEMA type_test.reports; "
            "CREATE TABLE type_test.reports.sales (amount INT); "
            'CREATE SCHEMA "type_test.reports"; '
            'CREATE TABLE "type_test.reports".sales (amount VARCHAR)'
        )
        assert (
            get_column_type('"memory"."type_test"."reports"."sales"', "amount")
            == "integer"
        )
        assert (
            get_column_type('"memory"."type_test.reports"."sales"', "amount")
            == "string"
        )
    finally:
        duckdb.execute(
            'DROP SCHEMA IF EXISTS type_test CASCADE; DROP SCHEMA IF EXISTS "type_test.reports" CASCADE'
        )


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    ("schema", "table"),
    [('column_type_"schema', "t.x"), ("column_type_schema", 't"x')],
)
def test_column_type_with_quoted_identifiers(schema: str, table: str) -> None:
    import duckdb

    from marimo._sql.sql_quoting import (
        quote_qualified_name,
        quote_sql_identifier,
    )

    qualified = quote_qualified_name("memory", schema, table)
    try:
        duckdb.execute(f"CREATE SCHEMA {quote_sql_identifier(schema)}")
        duckdb.execute(f'CREATE TABLE {qualified} ("c""x" INT)')
        assert get_column_type(qualified, 'c"x') == "integer"
    finally:
        duckdb.execute(
            f"DROP SCHEMA IF EXISTS memory.{quote_sql_identifier(schema)} CASCADE"
        )
