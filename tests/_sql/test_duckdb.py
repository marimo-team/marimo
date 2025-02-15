"""Tests for SQL engines."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Generator

import pytest

from marimo._data.models import Database, DataTable, DataTableColumn, Schema
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines import (
    DuckDBEngine,
)
from marimo._sql.sql import sql

HAS_DUCKDB = DependencyManager.duckdb.has()
HAS_PANDAS = DependencyManager.pandas.has()

if TYPE_CHECKING:
    import duckdb


@pytest.fixture
def duckdb_connection() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Create a DuckDB connection for testing."""

    import duckdb

    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE test (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255)
        );
        """
    )
    conn.execute(
        """
        INSERT INTO test VALUES
        (1, 'Alice'),
        (2, 'Bob'),
        (3, 'Charlie');
        """
    )
    sql("INSERT INTO test (id, name) VALUES (4, 'Rose')", engine=conn)
    yield conn
    conn.execute("DROP TABLE test")
    conn.close()


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_engine_dialect() -> None:
    """Test DuckDBEngine dialect property."""
    engine = DuckDBEngine(None)
    assert engine.dialect == "duckdb"


@pytest.mark.skipif(
    not HAS_DUCKDB or not HAS_PANDAS, reason="DuckDB and Pandas not installed"
)
def test_duckdb_engine_execute(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    """Test DuckDBEngine execute with both connection and no connection."""
    import pandas as pd
    import polars as pl

    # Test with explicit connection
    engine = DuckDBEngine(duckdb_connection)
    result = engine.execute("SELECT * FROM test ORDER BY id")
    assert isinstance(result, (pd.DataFrame, pl.DataFrame))
    assert len(result) == 4


expected_databases_with_conn = [
    Database(
        name="memory",
        dialect="duckdb",
        engine="test_duckdb",
        schemas=[
            Schema(
                name="main",
                tables=[
                    DataTable(
                        name="test",
                        source="memory",
                        source_type="connection",
                        num_rows=None,
                        num_columns=2,
                        variable_name=None,
                        engine="test_duckdb",
                        columns=[
                            DataTableColumn(
                                name="id",
                                type="integer",
                                external_type="INTEGER",
                                sample_values=[],
                            ),
                            DataTableColumn(
                                name="name",
                                type="string",
                                external_type="VARCHAR",
                                sample_values=[],
                            ),
                        ],
                    )
                ],
            )
        ],
    )
]


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_engine_get_databases(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    """Test DuckDBEngine get_databases method."""

    engine = DuckDBEngine(duckdb_connection, engine_name="test_duckdb")
    databases = engine.get_databases()

    assert databases == expected_databases_with_conn


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_engine_get_databases_no_conn() -> None:
    """Test DuckDBEngine get_databases method."""
    engine = DuckDBEngine()
    initial_databases = engine.get_databases()
    assert initial_databases == []

    engine.execute(
        "CREATE TABLE test (id INTEGER PRIMARY KEY, name VARCHAR(255))"
    )
    engine.execute(
        """
        INSERT INTO test VALUES
        (1, 'Alice'),
        (2, 'Bob'),
        (3, 'Charlie');
        """
    )
    databases = engine.get_databases()

    expected_databases = deepcopy(expected_databases_with_conn)
    expected_databases[0].engine = None
    expected_databases[0].schemas[0].tables[0].engine = None
    expected_databases[0].schemas[0].tables[0].source_type = "duckdb"
    expected_databases[0].schemas[0].tables[0].source = "memory"

    assert databases == expected_databases

    engine.execute("DROP TABLE test")
