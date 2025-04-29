"""General tests for the SQL engines."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.clickhouse import ClickhouseEmbedded
from marimo._sql.engines.duckdb import DuckDBEngine
from marimo._sql.engines.sqlalchemy import SQLAlchemyEngine
from marimo._sql.utils import raise_df_import_error, sql_type_to_data_type

HAS_DUCKDB = DependencyManager.duckdb.has()
HAS_SQLALCHEMY = DependencyManager.sqlalchemy.has()
HAS_CLICKHOUSE = DependencyManager.chdb.has()
HAS_PANDAS = DependencyManager.pandas.has()
HAS_POLARS = DependencyManager.polars.has()

UNUSED_DB_NAME = "unused_db"


@pytest.mark.skipif(
    not HAS_DUCKDB or not HAS_SQLALCHEMY or not HAS_PANDAS,
    reason="Duckdb, sqlalchemy and pandas not installed",
)
def test_engine_compatibility() -> None:
    """Test engine compatibility checks."""
    import duckdb
    import sqlalchemy as sa

    mock_duckdb = MagicMock(spec=duckdb.DuckDBPyConnection)
    mock_sqlalchemy = MagicMock(spec=sa.Engine)

    assert DuckDBEngine.is_compatible(mock_duckdb)
    assert not DuckDBEngine.is_compatible(mock_sqlalchemy)
    assert SQLAlchemyEngine.is_compatible(mock_sqlalchemy)
    assert not SQLAlchemyEngine.is_compatible(mock_duckdb)


def test_raise_df_import_error() -> None:
    """Test raise_df_import_error function."""
    with pytest.raises(ImportError):
        raise_df_import_error("test_pkg")


@pytest.mark.skipif(
    not (HAS_DUCKDB and HAS_SQLALCHEMY and HAS_CLICKHOUSE),
    reason="Duckdb, sqlalchemy, and Clickhouse not installed",
)
def test_engine_name_initialization() -> None:
    """Test engine name initialization."""
    import chdb
    import duckdb
    import sqlalchemy as sa

    duckdb_conn = duckdb.connect(":memory:")
    sqlite_engine = sa.create_engine("sqlite:///:memory:")
    clickhouse_conn = chdb.connect(":memory:")

    duck_engine = DuckDBEngine(duckdb_conn, engine_name="my_duck")
    sql_engine = SQLAlchemyEngine(sqlite_engine, engine_name="my_sql")
    clickhouse_engine = SQLAlchemyEngine(
        clickhouse_conn, engine_name="my_clickhouse"
    )

    assert duck_engine._engine_name == "my_duck"
    assert sql_engine._engine_name == "my_sql"
    assert clickhouse_engine._engine_name == "my_clickhouse"

    # Test default names
    duck_engine_default = DuckDBEngine(duckdb_conn)
    sql_engine_default = SQLAlchemyEngine(sqlite_engine)
    clickhouse_engine_default = ClickhouseEmbedded(clickhouse_conn)

    assert duck_engine_default._engine_name is None
    assert sql_engine_default._engine_name is None
    assert clickhouse_engine_default._engine_name is None

    duckdb_conn.close()
    clickhouse_conn.close()


@pytest.mark.skipif(not HAS_DUCKDB, reason="Duckdb not installed")
def test_duckdb_source_and_dialect() -> None:
    """Test DuckDBEngine source and dialect properties."""
    import duckdb

    duckdb_conn = duckdb.connect(":memory:")
    engine = DuckDBEngine(duckdb_conn)

    assert engine.source == "duckdb"
    assert engine.dialect == "duckdb"

    duckdb_conn.close()


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_source_and_dialect() -> None:
    """Test SQLAlchemyEngine source and dialect properties."""
    import sqlalchemy as sa

    # Test with SQLite
    sqlite_engine = sa.create_engine("sqlite:///:memory:")
    engine = SQLAlchemyEngine(sqlite_engine)

    assert engine.source == "sqlalchemy"
    assert engine.dialect == "sqlite"

    # We can test multiple dialects without mocking by creating different engines
    # Test with PostgreSQL dialect using a direct instance
    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"
    pg_engine = SQLAlchemyEngine(mock_engine)
    assert pg_engine.source == "sqlalchemy"
    assert pg_engine.dialect == "postgresql"


@pytest.mark.skipif(not HAS_DUCKDB, reason="Duckdb not installed")
def test_duckdb_get_current_database_and_schema() -> None:
    """Test DuckDBEngine get_current_database and get_current_schema methods."""
    import duckdb

    duckdb_conn = duckdb.connect(":memory:")
    engine = DuckDBEngine(duckdb_conn)

    # These should return values for an in-memory database
    assert engine.get_default_database() is not None
    assert engine.get_default_schema() is not None

    # Test error handling by closing the connection before calling methods
    duckdb_conn.close()
    assert engine.get_default_database() is None
    assert engine.get_default_schema() is None
    # Connection already closed, no need to close again


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_get_databases() -> None:
    """Test SQLAlchemyEngine get_databases method."""
    import sqlalchemy as sa

    # Create a SQLite engine
    sqlite_engine = sa.create_engine("sqlite:///:memory:")

    # Create a test table
    with sqlite_engine.connect() as conn:
        conn.execute(
            sa.text("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        )
        conn.commit()

    engine = SQLAlchemyEngine(sqlite_engine)

    # Test with different include parameters
    databases_minimal = engine.get_databases(
        include_schemas=False,
        include_tables=False,
        include_table_details=False,
    )
    assert len(databases_minimal) > 0
    # SQLite in-memory database name can be ':memory:' or empty depending on the SQLAlchemy version
    assert databases_minimal[0].name in ["", ":memory:"]
    assert databases_minimal[0].dialect == "sqlite"

    # Test with schemas included
    databases_with_schemas = engine.get_databases(
        include_schemas=True, include_tables=False, include_table_details=False
    )
    assert len(databases_with_schemas) > 0
    assert len(databases_with_schemas[0].schemas) > 0

    # Test with tables included
    databases_with_tables = engine.get_databases(
        include_schemas=True, include_tables=True, include_table_details=False
    )
    assert len(databases_with_tables) > 0
    assert len(databases_with_tables[0].schemas) > 0

    # At least one schema should have tables
    has_tables = False
    for schema in databases_with_tables[0].schemas:
        if len(schema.tables) > 0:
            has_tables = True
            break
    assert has_tables

    # Test auto discovery resolution
    assert engine._resolve_should_auto_discover(True) is True
    assert engine._resolve_should_auto_discover(False) is False
    assert (
        engine._resolve_should_auto_discover("auto") is True
    )  # SQLite is cheap discovery


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_get_table_details() -> None:
    """Test SQLAlchemyEngine get_table_details method."""
    import sqlalchemy as sa
    from sqlalchemy import Column, Integer, MetaData, String, Table

    # Create a SQLite engine
    sqlite_engine = sa.create_engine("sqlite:///:memory:")

    # Create a test table with schema
    metadata = MetaData()
    Table(
        "test_table",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String),
    )

    metadata.create_all(sqlite_engine)

    engine = SQLAlchemyEngine(sqlite_engine)

    # Get table details
    table_details = engine.get_table_details(
        table_name="test_table",
        schema_name="main",
        database_name=UNUSED_DB_NAME,
    )  # main is default schema in SQLite

    assert table_details is not None
    assert table_details.name == "test_table"
    assert table_details.num_columns == 2
    assert len(table_details.columns) == 2
    assert table_details.primary_keys == ["id"]

    # Test column types
    column_names = [col.name for col in table_details.columns]
    assert "id" in column_names
    assert "name" in column_names


@pytest.mark.skipif(
    not HAS_DUCKDB or not (HAS_PANDAS or HAS_POLARS),
    reason="Duckdb and either pandas or polars not installed",
)
def test_duckdb_execute() -> None:
    """Test DuckDBEngine execute method."""
    import duckdb

    duckdb_conn = duckdb.connect(":memory:")
    engine = DuckDBEngine(duckdb_conn)

    # Create a test table
    engine.execute("CREATE TABLE test (id INTEGER, name VARCHAR)")
    engine.execute("INSERT INTO test VALUES (1, 'test1'), (2, 'test2')")

    # Query the table
    result = engine.execute("SELECT * FROM test ORDER BY id")

    # Check result type based on available libraries
    if HAS_POLARS:
        import polars as pl

        assert isinstance(result, pl.DataFrame)
    elif HAS_PANDAS:
        import pandas as pd

        assert isinstance(result, pd.DataFrame)

    # Test with invalid query
    assert engine.execute("") is None

    duckdb_conn.close()


@pytest.mark.skipif(
    not HAS_SQLALCHEMY or not (HAS_PANDAS or HAS_POLARS),
    reason="SQLAlchemy and either pandas or polars not installed",
)
def test_sqlalchemy_execute() -> None:
    """Test SQLAlchemyEngine execute method."""
    import sqlalchemy as sa

    sqlite_engine = sa.create_engine("sqlite:///:memory:")
    engine = SQLAlchemyEngine(sqlite_engine)

    # Create a test table
    engine.execute("CREATE TABLE test (id INTEGER, name TEXT)")
    engine.execute("INSERT INTO test VALUES (1, 'test1'), (2, 'test2')")

    # Query the table
    result = engine.execute("SELECT * FROM test ORDER BY id")

    # Check result type based on available libraries
    if HAS_POLARS:
        import polars as pl

        assert isinstance(result, pl.DataFrame)
    elif HAS_PANDAS:
        import pandas as pd

        assert isinstance(result, pd.DataFrame)

    # Test with a query that doesn't return a result set
    assert engine.execute("PRAGMA journal_mode=WAL") is not None


def test_sql_type_to_data_type() -> None:
    """Test sql_type_to_data_type function."""
    # Now that the raise statement is removed, we can test directly
    # Test integer types
    for int_type in ["INTEGER", "INT", "BIGINT", "SERIAL"]:
        assert sql_type_to_data_type(int_type) == "integer"

    # Test float types
    for float_type in ["FLOAT", "DOUBLE", "DECIMAL", "NUMERIC"]:
        assert sql_type_to_data_type(float_type) == "number"

    # Test datetime types
    for dt_type in ["TIMESTAMP", "DATETIME"]:
        assert sql_type_to_data_type(dt_type) == "datetime"

    # Test date type
    assert sql_type_to_data_type("DATE") == "date"

    # Test boolean type
    assert sql_type_to_data_type("BOOLEAN") == "boolean"

    # Test string types
    for str_type in ["VARCHAR", "CHAR", "TEXT"]:
        assert sql_type_to_data_type(str_type) == "string"

    # Test unknown type
    assert sql_type_to_data_type("UNKNOWN_TYPE") == "string"


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_type_conversion() -> None:
    """Test SQLAlchemyEngine _get_python_type and _get_generic_type methods."""
    import sqlalchemy as sa
    from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String

    sqlite_engine = sa.create_engine("sqlite:///:memory:")
    engine = SQLAlchemyEngine(sqlite_engine)

    # Test with various SQLAlchemy types
    assert engine._get_python_type(Integer()) == "integer"
    assert engine._get_python_type(String()) == "string"
    assert engine._get_python_type(Float()) == "number"
    assert engine._get_python_type(Boolean()) == "boolean"
    assert engine._get_python_type(DateTime()) == "datetime"
    # SQLAlchemy's Date type might be mapped to 'datetime' in some versions
    assert engine._get_python_type(Date()) in ["date", "datetime"]

    # Test with a custom type that raises NotImplementedError
    class CustomType(sa.types.TypeEngine):
        @property
        def python_type(self) -> None:
            raise NotImplementedError("Not implemented")

    assert engine._get_python_type(CustomType()) is None
