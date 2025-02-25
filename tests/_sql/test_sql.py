"""Tests for SQL functionality."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._sql.sql import _query_includes_limit, sql

if TYPE_CHECKING:
    from collections.abc import Generator

    import duckdb
    import sqlalchemy as sa


HAS_DUCKDB = DependencyManager.duckdb.has()
HAS_SQLALCHEMY = DependencyManager.sqlalchemy.has()
HAS_POLARS = DependencyManager.polars.has()
HAS_PANDAS = DependencyManager.pandas.has()
HAS_SQLGLOT = DependencyManager.sqlglot.has()


@pytest.fixture
def sqlite_engine() -> sa.Engine:
    """Create a temporary SQLite database for testing."""
    import sqlalchemy as sa

    engine = sa.create_engine("sqlite:///:memory:")
    sql(
        """
        CREATE TABLE test (
            id INTEGER PRIMARY KEY,
            name TEXT
        );
        """,
        engine=engine,
    )
    sql(
        """
        INSERT INTO test VALUES
        (1, 'Alice'),
        (2, 'Bob'),
        (3, 'Charlie');
        """,
        engine=engine,
    )
    return engine


@pytest.fixture
def duckdb_connection() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Create a DuckDB connection for testing."""
    import duckdb

    conn = duckdb.connect(":memory:")
    sql(
        """
        CREATE TABLE test (
            id INTEGER PRIMARY KEY,
            name TEXT
        );
        """,
        engine=conn,
    )
    sql(
        """
        INSERT INTO test VALUES
        (1, 'Alice'),
        (2, 'Bob'),
        (3, 'Charlie');
        """,
        engine=conn,
    )

    yield conn
    conn.close()


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sql_with_different_engines(
    sqlite_engine: sa.Engine, duckdb_connection: duckdb.DuckDBPyConnection
) -> None:
    """Test sql function with different engines."""
    import pandas as pd
    import polars as pl

    # Test with SQLAlchemy engine
    result = sql("SELECT * FROM test ORDER BY id", engine=sqlite_engine)
    assert isinstance(result, (pd.DataFrame, pl.DataFrame))
    assert len(result) == 3

    # Test with DuckDB connection
    result = sql("SELECT * FROM test ORDER BY id", engine=duckdb_connection)
    assert isinstance(result, (pd.DataFrame, pl.DataFrame))
    assert len(result) == 3

    # Test with default DuckDB
    # df = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
    # with patch.dict(globals(), {"df": df}):
    #     result = sql("SELECT * FROM df")
    #     assert isinstance(result, (pd.DataFrame, pl.DataFrame))
    #     assert len(result) == 2


def test_sql_with_invalid_engine() -> None:
    """Test sql function with invalid engine."""
    with pytest.raises(ValueError, match="Unsupported engine"):
        sql("SELECT 1", engine="invalid")


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_empty_sql(
    sqlite_engine: sa.Engine, duckdb_connection: duckdb.DuckDBPyConnection
) -> None:
    result = sql("", engine=duckdb_connection)
    assert result is None

    result = sql("", engine=sqlite_engine)
    assert result is None


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_invalid_sql(
    sqlite_engine: sa.Engine, duckdb_connection: duckdb.DuckDBPyConnection
) -> None:
    import duckdb
    import sqlalchemy

    with pytest.raises(duckdb.Error):
        sql("SELECT *", engine=duckdb_connection)

    with pytest.raises(sqlalchemy.exc.StatementError):
        sql("SELECT *", engine=sqlite_engine)


# TODO
@pytest.mark.skipif(not HAS_PANDAS, reason="Pandas not installed")
def test_sql_with_limit() -> None:
    """Test sql function respects LIMIT clause and environment variable."""
    import pandas as pd

    _df = pd.DataFrame(
        {"id": range(10), "name": [f"User{i}" for i in range(10)]}
    )

    # Test with explicit LIMIT
    # with patch.dict(globals(), {"df": df}):
    # result = sql("SELECT * FROM df LIMIT 5")
    # assert len(result) == 5

    # Test with environment variable limit
    # with patch.dict(os.environ, {"MARIMO_SQL_DEFAULT_LIMIT": "3"}):
    #     with patch.dict(globals(), {"df": df}):
    #         result = sql("SELECT * FROM df")
    #         assert len(result) == 3


@pytest.mark.skipif(not HAS_PANDAS, reason="Pandas not installed")
def test_sql_output_formatting() -> None:
    """Test sql function output formatting."""
    import pandas as pd

    # import polars as pl

    _df = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})

    # Test with output=False
    # with patch.dict(globals(), {"df": df}):
    #     result = sql("SELECT * FROM df", output=False)
    #     assert isinstance(result, (pd.DataFrame, pl.DataFrame))
    #     assert len(result) == 2

    # Test with output=True (mock replace function)
    # with patch("marimo._runtime.output.replace") as mock_replace:
    #     with patch.dict(globals(), {"df": df}):
    #         sql("SELECT * FROM df", output=True)
    #         mock_replace.assert_called_once()


@pytest.mark.xfail(
    reason="Multiple select statements are not supported for sqlite"
)
@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sql_multiple_statements(sqlite_engine: sa.Engine) -> None:
    import pandas as pd
    import polars as pl

    multi_statement = """
    SELECT 1, 2;
    SELECT 3, 4;
    """
    result = sql(multi_statement, engine=sqlite_engine)
    assert isinstance(result, (pd.DataFrame, pl.DataFrame))
    assert len(result) == 2


@pytest.mark.skipif(not HAS_SQLGLOT, reason="sqlglot not installed")
def test_query_includes_limit() -> None:
    """Test _query_includes_limit function."""
    # Test queries with LIMIT
    assert _query_includes_limit("SELECT * FROM table LIMIT 5")
    assert _query_includes_limit("SELECT * FROM table LIMIT\n5")
    assert _query_includes_limit("SELECT * FROM table limit\n5")
    assert _query_includes_limit(
        """
        SELECT *
        FROM table
        LIMIT 5
        """
    )

    # Test queries without LIMIT
    assert not _query_includes_limit("SELECT * FROM table")
    assert not _query_includes_limit("SELECT LIMIT_COL FROM table")
    assert not _query_includes_limit("-- LIMIT 5\nSELECT * FROM table")

    # Test invalid SQL
    assert not _query_includes_limit("NOT A VALID SQL QUERY")
    assert not _query_includes_limit("")
    assert not _query_includes_limit("INSERT INTO t VALUES (1, 2, 3)")

    # Multiple queries
    assert (
        _query_includes_limit("SELECT * FROM t; SELECT * FROM t2 LIMIT 5")
        is True
    )
    assert (
        _query_includes_limit("SELECT * FROM t LIMIT 5; SELECT * FROM t2")
        is False
    )


@patch("marimo._sql.sql.replace")
@pytest.mark.skipif(not HAS_POLARS and HAS_DUCKDB, reason="polars is required")
def test_applies_limit(mock_replace: MagicMock) -> None:
    import duckdb

    with patch.dict(os.environ, {"MARIMO_SQL_DEFAULT_LIMIT": "300"}):
        duckdb.sql("CREATE OR REPLACE TABLE t AS SELECT * FROM range(1000)")
        mock_replace.assert_not_called()

        table: ui.table

        # No limit, fallback to 300
        assert len(sql("SELECT * FROM t")) == 300
        mock_replace.assert_called_once()
        table = mock_replace.call_args[0][0]
        assert table._component_args["total-rows"] == "too_many"
        assert table._component_args["pagination"] is True
        assert len(table._data) == 300
        assert table._searched_manager.get_num_rows() == 300

        # Limit 10
        mock_replace.reset_mock()
        assert len(sql("SELECT * FROM t LIMIT 10")) == 10
        mock_replace.assert_called_once()
        table = mock_replace.call_args[0][0]
        assert table._component_args["total-rows"] == 10
        assert table._component_args["pagination"] is True
        assert len(table._data) == 10
        assert table._searched_manager.get_num_rows() == 10

        # Limit 400
        mock_replace.reset_mock()
        assert len(sql("SELECT * FROM t LIMIT 400")) == 400
        mock_replace.assert_called_once()
        table = mock_replace.call_args[0][0]
        assert table._component_args["total-rows"] == 400
        assert table._component_args["pagination"] is True
        assert len(table._data) == 400
        assert table._searched_manager.get_num_rows() == 400

    # Limit above 20_0000 (which is the mo.ui.table cutoff)
    mock_replace.reset_mock()
    duckdb.sql(
        "CREATE OR REPLACE TABLE big_table AS SELECT * FROM range(30_000)"
    )
    assert len(sql("SELECT * FROM big_table LIMIT 25_000")) == 25_000
    mock_replace.assert_called_once()
    table = mock_replace.call_args[0][0]
    assert table._component_args["total-rows"] == 25_000
    assert table._component_args["pagination"] is True
    assert len(table._data) == 25_000
    assert table._searched_manager.get_num_rows() == 25_000


@pytest.mark.skipif(
    DependencyManager.duckdb.has(), reason="must be missing duckdb"
)
def test_sql_raises_error_without_duckdb():
    with pytest.raises(ModuleNotFoundError):
        sql("SELECT * FROM t")


@patch("marimo._sql.sql.replace")
@pytest.mark.skipif(not HAS_POLARS and HAS_DUCKDB, reason="polars is required")
def test_sql_output_flag(mock_replace: MagicMock) -> None:
    import duckdb
    import polars as pl

    from marimo._sql.sql import sql

    # Create a test table
    duckdb.sql(
        "CREATE OR REPLACE TABLE test_table_2 AS SELECT * FROM range(10)"
    )

    # Test when output is None (default, True)
    result = sql("SELECT * FROM test_table_2")
    assert isinstance(result, pl.DataFrame)
    mock_replace.assert_called_once()
    mock_replace.reset_mock()

    # Test when output is False
    result = sql("SELECT * FROM test_table_2", output=False)
    assert isinstance(result, pl.DataFrame)
    mock_replace.assert_not_called()
    mock_replace.reset_mock()

    # Test when output is True
    result = sql("SELECT * FROM test_table_2", output=True)
    assert isinstance(result, pl.DataFrame)
    mock_replace.assert_called_once()
    mock_replace.reset_mock()

    # Clean up
    duckdb.sql("DROP TABLE test_table_2")
