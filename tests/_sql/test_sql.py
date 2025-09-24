# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins import ui
from marimo._sql.engines.ibis import IbisEngine
from marimo._sql.engines.sqlalchemy import SQLAlchemyEngine
from marimo._sql.sql import _query_includes_limit, sql
from marimo._sql.utils import (
    extract_explain_content,
    is_explain_query,
    is_query_empty,
    wrap_query_with_explain,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    import duckdb
    import sqlalchemy as sa


HAS_DUCKDB = DependencyManager.duckdb.has()
HAS_SQLALCHEMY = DependencyManager.sqlalchemy.has()
HAS_IBIS = DependencyManager.ibis.has()
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


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sql_with_cursor_result(sqlite_engine: sa.Engine):
    from sqlalchemy.engine import CursorResult

    with patch.object(
        SQLAlchemyEngine, "sql_output_format", return_value="native"
    ):
        result = sql("SELECT * FROM test", engine=sqlite_engine)
        assert isinstance(result, CursorResult)


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_sql_with_ibis_expression_result():
    import ibis
    from ibis import Expr

    duckdb_backend = ibis.duckdb.connect()  # in-memory
    # Create a test table with data
    data_table = ibis.memtable({"id": [1, 2], "name": ["test1", "test2"]})
    duckdb_backend.create_table("test", obj=data_table)

    with patch.object(IbisEngine, "sql_output_format", return_value="native"):
        result = sql("SELECT * FROM test", engine=duckdb_backend)
        assert isinstance(result, Expr)


class TestExplainQueries:
    def test_is_explain_query(self):
        """Test is_explain_query function."""
        # Test valid EXPLAIN queries
        assert is_explain_query("EXPLAIN SELECT 1")
        assert is_explain_query("explain SELECT 1")
        assert is_explain_query("  EXPLAIN SELECT 1")
        assert is_explain_query("\tEXPLAIN SELECT 1")
        assert is_explain_query("\nEXPLAIN SELECT 1")
        assert is_explain_query("EXPLAIN (FORMAT JSON) SELECT 1")
        assert is_explain_query("EXPLAIN ANALYZE SELECT 1")
        assert is_explain_query("EXPLAIN QUERY PLAN SELECT 1")

        # Test non-EXPLAIN queries
        assert not is_explain_query("SELECT 1")
        assert not is_explain_query("INSERT INTO t VALUES (1)")
        assert not is_explain_query("UPDATE t SET col = 1")
        assert not is_explain_query("DELETE FROM t")
        assert not is_explain_query("CREATE TABLE t (id INT)")
        assert not is_explain_query("")
        assert not is_explain_query("   ")

        # Test edge cases
        assert not is_explain_query("EXPLAINED")  # Not exactly "explain"
        assert not is_explain_query("EXPLAINING")  # Not exactly "explain"
        assert not is_explain_query(
            "-- EXPLAIN SELECT 1"
        )  # Comment, not actual query

    @pytest.fixture
    def explain_df_data(self) -> dict[str, list[str]]:
        return {
            "explain_key": ["physical_plan", "logical_plan"],
            "explain_value": [
                "┌─────────────────────────────────────┐\n│              PROJECTION               │\n└─────────────────────────────────────┘",
                "┌─────────────────────────────────────┐\n│              SELECTION                │\n└─────────────────────────────────────┘",
            ],
        }

    @pytest.mark.skipif(not HAS_POLARS, reason="Polars not installed")
    def test_extract_explain_content_polars(
        self, explain_df_data: dict[str, list[str]]
    ):
        """Test extract_explain_content with polars DataFrames."""
        import polars as pl

        # Test with regular DataFrame
        df = pl.DataFrame(explain_df_data)

        expected_rendering = """shape: (2, 2)
┌───────────────┬───────────────────────────────────────────┐
│ explain_key   ┆ explain_value                             │
│ ---           ┆ ---                                       │
│ str           ┆ str                                       │
╞═══════════════╪═══════════════════════════════════════════╡
│ physical_plan ┆ ┌─────────────────────────────────────┐   │
│               ┆ │              PROJECTION               │ │
│               ┆ └─────────────────────────────────────┘   │
│ logical_plan  ┆ ┌─────────────────────────────────────┐   │
│               ┆ │              SELECTION                │ │
│               ┆ └─────────────────────────────────────┘   │
└───────────────┴───────────────────────────────────────────┘"""

        result = extract_explain_content(df)
        assert result == expected_rendering

        # Test with LazyFrame
        lazy_df = df.lazy()
        result = extract_explain_content(lazy_df)
        assert result == expected_rendering

    @pytest.mark.skipif(not HAS_PANDAS, reason="Pandas not installed")
    def test_extract_explain_content_pandas(
        self, explain_df_data: dict[str, list[str]]
    ):
        """Test extract_explain_content with pandas DataFrames."""
        import pandas as pd

        df = pd.DataFrame(explain_df_data)

        result = extract_explain_content(df)
        assert (
            result
            == """physical_plan
┌─────────────────────────────────────┐
│              PROJECTION               │
└─────────────────────────────────────┘
logical_plan
┌─────────────────────────────────────┐
│              SELECTION                │
└─────────────────────────────────────┘"""
        )

    def test_extract_explain_content_fallback(self):
        """Test extract_explain_content fallback for non-DataFrame objects."""
        # Test with non-DataFrame object
        result = extract_explain_content("not a dataframe")
        assert isinstance(result, str)
        assert "not a dataframe" in result

        # Test with None
        result = extract_explain_content(None)
        assert isinstance(result, str)
        assert "None" in result

    @pytest.mark.skipif(not HAS_POLARS, reason="Polars not installed")
    def test_extract_explain_content_error_handling(self):
        """Test extract_explain_content error handling."""

        # Create a mock DataFrame that will raise an error
        class MockDataFrame:
            def __init__(self):
                pass

            def __str__(self):
                raise RuntimeError("Test error")

        mock_df = MockDataFrame()
        result = extract_explain_content(mock_df)
        assert isinstance(result, str)
        assert "MockDataFrame" in result  # Should fallback to repr

    @patch("marimo._sql.sql.replace")
    @pytest.mark.skipif(
        not HAS_POLARS or not HAS_DUCKDB, reason="polars and duckdb required"
    )
    def test_sql_explain_query_display(self, mock_replace):
        """Test that EXPLAIN queries are displayed as plain text."""
        import duckdb
        import polars as pl

        # Create a test table
        duckdb.sql(
            "CREATE OR REPLACE TABLE test_explain AS SELECT * FROM range(5)"
        )

        # Test EXPLAIN query
        result = sql("EXPLAIN SELECT * FROM test_explain")
        assert isinstance(result, pl.DataFrame)

        # Should call replace with plain_text
        mock_replace.assert_called_once()
        call_args = mock_replace.call_args[0][0]

        # The call should be a plain_text object
        assert hasattr(call_args, "text")
        assert isinstance(call_args.text, str)

        # Clean up
        duckdb.sql("DROP TABLE test_explain")

    def test_wrap_query_with_explain(self):
        """Test wrap_query_with_explain function."""
        assert (
            wrap_query_with_explain("SELECT * FROM t")
            == "EXPLAIN SELECT * FROM t"
        )
        assert (
            wrap_query_with_explain("EXPLAIN SELECT * FROM t")
            == "EXPLAIN SELECT * FROM t"
        )
        assert (
            wrap_query_with_explain("EXPLAIN (FORMAT JSON) SELECT * FROM t")
            == "EXPLAIN (FORMAT JSON) SELECT * FROM t"
        )
        assert (
            wrap_query_with_explain("EXPLAIN ANALYZE SELECT * FROM t")
            == "EXPLAIN ANALYZE SELECT * FROM t"
        )
        assert (
            wrap_query_with_explain("EXPLAIN QUERY PLAN SELECT * FROM t")
            == "EXPLAIN QUERY PLAN SELECT * FROM t"
        )

    def test_is_query_empty(self):
        """Test is_query_empty function."""

        assert is_query_empty("SELECT * FROM t") is False
        assert is_query_empty("INSERT INTO t VALUES (1)") is False
        assert is_query_empty("UPDATE t SET col = 1") is False
        assert is_query_empty("DELETE FROM t") is False
        assert is_query_empty("CREATE TABLE t (id INT)") is False
        assert is_query_empty("") is True
        assert is_query_empty("   ") is True

        # Comments
        assert is_query_empty("-- SELECT * FROM t") is True
        assert is_query_empty("/* SELECT * FROM t */") is True
        assert (
            is_query_empty("""
        -- SELECT * FROM t
        /* SELECT * FROM t */
        """)
            is True
        )
        assert is_query_empty(" -- some query with space") is True

        # Invalid SQL
        assert is_query_empty("NOT A VALID SQL QUERY") is False
        assert is_query_empty("SELECT * FROM t WHERE x = '") is False
