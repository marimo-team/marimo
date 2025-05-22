"""Tests for SQL engines."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest

from marimo._data.models import Database, DataTable, DataTableColumn, Schema
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.duckdb import DuckDBEngine
from marimo._sql.engines.types import EngineCatalog, QueryEngine
from marimo._sql.sql import sql
from marimo._types.ids import VariableName

HAS_DUCKDB = DependencyManager.duckdb.has()
HAS_PANDAS = DependencyManager.pandas.has()
HAS_POLARS = DependencyManager.polars.has()

if TYPE_CHECKING:
    from collections.abc import Generator

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
    engine = DuckDBEngine(None, engine_name=None)
    assert engine.dialect == "duckdb"


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_engine_is_instance() -> None:
    """Test DuckDBEngine is an instance of the correct types."""
    engine = DuckDBEngine(None, engine_name=None)
    assert isinstance(engine, DuckDBEngine)
    assert isinstance(engine, EngineCatalog)
    assert isinstance(engine, QueryEngine)


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
    engine = DuckDBEngine(duckdb_connection, engine_name=None)
    result = engine.execute("SELECT * FROM test ORDER BY id")
    assert isinstance(result, (pd.DataFrame, pl.DataFrame))
    assert len(result) == 4


expected_databases_with_conn = [
    Database(
        name="memory",
        dialect="duckdb",
        engine=VariableName("test_duckdb"),
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
                        engine=VariableName("test_duckdb"),
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

    engine = DuckDBEngine(
        duckdb_connection, engine_name=VariableName("test_duckdb")
    )
    databases = engine.get_databases(
        include_schemas=True, include_tables=True, include_table_details=True
    )

    assert databases == expected_databases_with_conn


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_engine_get_databases_no_conn() -> None:
    """Test DuckDBEngine get_databases method."""
    engine = DuckDBEngine(None, engine_name=None)
    initial_databases = engine.get_databases(
        include_schemas=False,
        include_table_details=False,
        include_tables=False,
    )
    assert initial_databases == []
    assert engine.get_default_database() == "memory"
    assert engine.get_default_schema() == "main"

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
    databases = engine.get_databases(
        include_schemas=True, include_tables=True, include_table_details=True
    )

    expected_databases = deepcopy(expected_databases_with_conn)
    expected_databases[0].engine = None
    expected_databases[0].schemas[0].tables[0].engine = None
    expected_databases[0].schemas[0].tables[0].source_type = "duckdb"
    expected_databases[0].schemas[0].tables[0].source = "memory"

    assert databases == expected_databases

    engine.execute("DROP TABLE test")


@pytest.mark.skipif(not HAS_DUCKDB, reason="duckdb not installed")
def test_get_current_database_schema() -> None:
    import duckdb

    engine = duckdb.connect(":memory:")
    duckdb_engine = DuckDBEngine(
        engine, engine_name=VariableName("test_duckdb")
    )

    assert duckdb_engine.get_default_database() == "memory"
    assert duckdb_engine.get_default_schema() == "main"

    sql("CREATE SCHEMA test_schema;", engine=engine)
    sql("CREATE TABLE test_schema.test_table (id INTEGER);", engine=engine)
    sql("USE test_schema;", engine=engine)

    assert duckdb_engine.get_default_database() == "memory"
    assert duckdb_engine.get_default_schema() == "test_schema"

    sql("DROP TABLE test_schema.test_table;", engine=engine)
    sql("DROP SCHEMA test_schema;", engine=engine)


@pytest.mark.skipif(
    not HAS_DUCKDB or not HAS_POLARS or not HAS_PANDAS,
    reason="duckdb, polars and pandas not installed",
)
def test_duckdb_engine_execute_polars_fallback() -> None:
    import pandas as pd

    engine = DuckDBEngine(None, engine_name=VariableName("test_duckdb"))
    # This dtype is currently not supported by polars
    result = engine.execute(
        "select to_days(cast((current_date - DATE '2025-01-01') as INTEGER));"
    )
    assert isinstance(result, pd.DataFrame)


@pytest.mark.skipif(
    not HAS_DUCKDB or not HAS_POLARS or not HAS_PANDAS,
    reason="DuckDB, Polars, and Pandas not installed",
)
def test_duckdb_engine_sql_output_formats(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    """Test DuckDBEngine execute with different SQL output formats."""
    from unittest import mock

    import pandas as pd
    import polars as pl

    # Test with polars output format
    with mock.patch.object(
        DuckDBEngine, "sql_output_format", return_value="polars"
    ):
        engine = DuckDBEngine(
            duckdb_connection, engine_name=VariableName("test_duckdb")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, pl.DataFrame)
        assert len(result) == 4

    # Test with lazy-polars output format
    with mock.patch.object(
        DuckDBEngine, "sql_output_format", return_value="lazy-polars"
    ):
        engine = DuckDBEngine(
            duckdb_connection, engine_name=VariableName("test_duckdb")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, pl.LazyFrame)
        assert len(result.collect()) == 4

    # Test with pandas output format
    with mock.patch.object(
        DuckDBEngine, "sql_output_format", return_value="pandas"
    ):
        engine = DuckDBEngine(
            duckdb_connection, engine_name=VariableName("test_duckdb")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 4

    # Test with native output format
    with mock.patch.object(
        DuckDBEngine, "sql_output_format", return_value="native"
    ):
        engine = DuckDBEngine(
            duckdb_connection, engine_name=VariableName("test_duckdb")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert not isinstance(
            result, (pd.DataFrame, pl.DataFrame, pl.LazyFrame)
        )
        # DuckDB native result has a different interface than SQLAlchemy
        assert hasattr(result, "fetchall") or hasattr(result, "fetch_df")

    # Test with auto output format (should use polars if available)
    with mock.patch.object(
        DuckDBEngine, "sql_output_format", return_value="auto"
    ):
        engine = DuckDBEngine(
            duckdb_connection, engine_name=VariableName("test_duckdb")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, (pd.DataFrame, pl.DataFrame))
        assert len(result) == 4
