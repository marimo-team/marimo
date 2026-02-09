# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import os
import tempfile
from copy import deepcopy
from typing import TYPE_CHECKING

import pytest

from marimo._convert.common.format import SQL_QUOTE_PREFIX
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
    assert initial_databases == [
        Database(name="memory", dialect="duckdb", schemas=[])
    ]
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


def _make_sql_string(body: str, **local_vars: object) -> str:
    """Build and evaluate a SQL string using SQL_QUOTE_PREFIX.

    Simulates what the generated marimo code looks like at runtime:
        {SQL_QUOTE_PREFIX}\"\"\"{body}\"\"\"

    Args:
        body: The SQL string body. Use ``{var}`` for interpolation
            and ``{{`` / ``}}`` for literal braces.
        **local_vars: Variables available for f-string interpolation.

    Returns:
        The evaluated string.
    """
    # Braces in *body* that should be interpolated are already single,
    # e.g. "{limit}".  The outer f-string here must not touch them,
    # so we escape them for the outer layer and let exec handle them.
    escaped = body.replace("{", "{{").replace("}", "}}")
    # Now un-escape the ones that were *originally* doubled (literal braces).
    # Original `{{` in body → `{{{{` after first replace → should become `{{`
    # But simpler: just build the code string directly without an outer f-string.
    code = f"__result = {SQL_QUOTE_PREFIX}" + '"""' + body + '"""'
    ns: dict[str, object] = dict(local_vars)
    exec(code, ns)  # noqa: S102
    return str(ns["__result"])


@pytest.mark.skipif(
    not HAS_DUCKDB or not HAS_POLARS,
    reason="DuckDB and Polars not installed",
)
class TestDuckDBWithSqlQuotePrefix:
    """Test that SQL_QUOTE_PREFIX strings work correctly with DuckDB.

    This verifies the fix for issue #8179: Windows backslash paths in SQL
    cells causing unicode escape errors. SQL cells now use the prefix
    defined by SQL_QUOTE_PREFIX (currently ``rf``) instead of plain ``f``.

    Tests focus on backslash handling, escape sequences, curly braces,
    and f-string interpolation — the behaviors affected by the prefix.

    All string construction goes through ``_make_sql_string`` so the
    tests automatically adapt if SQL_QUOTE_PREFIX ever changes.
    """

    def test_preserves_backslashes(self) -> None:
        """Test that SQL_QUOTE_PREFIX strings preserve literal backslashes.

        This is the core issue from #8179: pasting Windows paths like
        C:\\Users\\data\\file.csv should not cause unicode escape errors.
        """
        path = _make_sql_string(r"C:\Users\data\file.csv")
        assert path == r"C:\Users\data\file.csv"
        assert path.count("\\") == 3

    def test_special_escape_sequences(self) -> None:
        r"""Test that common escape sequences are literal.

        In a plain f-string: \n → newline, \t → tab, \r → carriage return.
        With SQL_QUOTE_PREFIX: \n, \t, \r remain as two-character sequences.
        """
        s = _make_sql_string(r"\n\t\r\0\a\b")
        assert s == "\\n\\t\\r\\0\\a\\b"
        assert len(s) == 12  # 6 pairs of 2 chars, not 6 single chars

    def test_unicode_escape_sequences(self) -> None:
        r"""Test that \U and \u (unicode escapes) are literal.

        This is the exact failure from #8179: plain f-strings interpret \U
        as a 32-bit unicode escape and \u as a 16-bit unicode escape.
        """
        s = _make_sql_string(r"\Users\ubuntu\unique")
        assert s == "\\Users\\ubuntu\\unique"
        assert "\\U" in s  # literal backslash + U, not a unicode char

    def test_hex_escape_sequences(self) -> None:
        r"""Test that \x (hex escape) is literal."""
        s = _make_sql_string(r"\x00\xff")
        assert s == "\\x00\\xff"
        assert len(s) == 8  # Not the 2 bytes from a regular string

    def test_fstring_interpolation_still_works(self) -> None:
        """Test that {expr} interpolation works."""
        limit = 5
        query = _make_sql_string(
            "SELECT * FROM range(10) LIMIT {limit}", limit=limit
        )
        result = sql(query)
        assert len(result) == 5

    def test_complex_interpolation(self) -> None:
        """Test complex f-string expressions."""
        import duckdb

        duckdb.sql(
            "CREATE OR REPLACE TABLE rf_complex AS "
            "SELECT * FROM range(20) t(id)"
        )
        in_clause = ",".join(str(v) for v in [1, 2, 3])
        query = _make_sql_string(
            "SELECT * FROM rf_complex WHERE id IN ({in_clause})",
            in_clause=in_clause,
        )
        result = sql(query)
        assert len(result) == 3
        duckdb.sql("DROP TABLE rf_complex")

    def test_escaped_curly_braces(self) -> None:
        """Test escaped curly braces (literal braces in SQL).

        Double braces {{ }} produce literal { } in f-strings.
        This must still work with SQL_QUOTE_PREFIX.
        """
        query = _make_sql_string("SELECT {{'key': 'value'}} AS json_str")
        result = sql(query)
        assert result is not None
        assert len(result) == 1

    def test_multiple_interpolations(self) -> None:
        """Test multiple f-string interpolations."""
        query = _make_sql_string(
            """
            SELECT * FROM range(100) t(id)
            WHERE id >= {min_val} AND id < {max_val}
            LIMIT {limit}
        """,
            min_val=0,
            max_val=5,
            limit=3,
        )
        result = sql(query)
        assert len(result) == 3

    def test_backslash_in_like_pattern(self) -> None:
        """Test backslash in LIKE patterns."""
        query = _make_sql_string(
            r"SELECT 'test\path' LIKE '%\%' AS has_backslash"
        )
        result = sql(query)
        assert result is not None

    def test_windows_path_in_string_literal(self) -> None:
        """Test Windows paths inside SQL string literals."""
        query = _make_sql_string(r"SELECT 'C:\Users\data\file.csv' AS path")
        result = sql(query)
        assert result is not None
        assert len(result) == 1

    def test_read_csv_with_path(self) -> None:
        """Test READ_CSV with a real file path."""
        import polars as pl

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write("id,name\n1,Alice\n2,Bob\n")
            csv_path = f.name

        try:
            normalized = csv_path.replace("\\", "/")
            query = _make_sql_string(
                "SELECT * FROM read_csv('{normalized}')",
                normalized=normalized,
            )
            result = sql(query)
            assert isinstance(result, pl.DataFrame)
            assert len(result) == 2
        finally:
            os.unlink(csv_path)

    def test_backslash_with_interpolation(self) -> None:
        """Test that backslashes and interpolation coexist correctly."""
        query = _make_sql_string(
            r"SELECT '\Users' AS path, * FROM {table}",
            table="range(3)",
        )
        result = sql(query)
        assert len(result) == 3

    def test_regex_pattern(self) -> None:
        """Test regex patterns containing backslashes.

        DuckDB supports regexp_matches which uses backslash-heavy patterns.
        """
        query = _make_sql_string(
            r"SELECT regexp_matches('hello123', '\d+') AS has_digits"
        )
        result = sql(query)
        assert result is not None
        assert len(result) == 1

    def test_nested_quotes_and_backslashes(self) -> None:
        """Test a mix of quotes and backslashes."""
        query = _make_sql_string(
            r"""SELECT 'it''s a \"test\" with C:\path' AS mixed"""
        )
        result = sql(query)
        assert result is not None
        assert len(result) == 1
