"""Tests for SQL engines."""

from __future__ import annotations

from typing import TYPE_CHECKING, Generator
from unittest.mock import MagicMock

import pytest

from marimo._data.models import DataTable
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines import (
    DuckDBEngine,
    SQLAlchemyEngine,
    raise_df_import_error,
)
from marimo._sql.sql import sql

HAS_DUCKDB = DependencyManager.duckdb.has()
HAS_SQLALCHEMY = DependencyManager.sqlalchemy.has()
HAS_POLARS = DependencyManager.polars.has()
HAS_PANDAS = DependencyManager.pandas.has()

if TYPE_CHECKING:
    import duckdb
    import sqlalchemy as sa


@pytest.fixture
def sqlite_engine() -> sa.Engine:
    """Create a temporary SQLite database for testing."""

    import sqlalchemy as sa
    from sqlalchemy import text

    engine = sa.create_engine("sqlite:///:memory:")

    # Test if standard syntax works
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE test (
                    id INTEGER PRIMARY KEY,
                    name TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO test (id, name) VALUES
                (1, 'Alice'),
                (2, 'Bob'),
                (3, 'Charlie')
                """
            )
        )

    # Test if mo.sql works
    sql("INSERT INTO test (id, name) VALUES (4, 'Rose')", engine=engine)
    return engine


@pytest.fixture
def duckdb_connection() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Create a DuckDB connection for testing."""

    import duckdb

    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE test (
            id INTEGER PRIMARY KEY,
            name TEXT
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
    conn.close()


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_engine_dialect() -> None:
    """Test DuckDBEngine dialect property."""
    engine = DuckDBEngine(None)
    assert engine.dialect == "duckdb"


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_engine_dialect(sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine dialect property."""
    engine = SQLAlchemyEngine(sqlite_engine)
    assert engine.dialect == "sqlite"


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


@pytest.mark.skipif(
    not HAS_SQLALCHEMY or not HAS_PANDAS,
    reason="SQLAlchemy and Pandas not installed",
)
def test_sqlalchemy_engine_execute(sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine execute."""
    import pandas as pd
    import polars as pl

    engine = SQLAlchemyEngine(sqlite_engine)
    result = engine.execute("SELECT * FROM test ORDER BY id")
    assert isinstance(result, (pd.DataFrame, pl.DataFrame))
    assert len(result) == 4


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


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_engine_get_tables(sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine get_tables method."""
    engine = SQLAlchemyEngine(sqlite_engine, engine_name="test_sqlite")
    tables = engine.get_tables()

    assert isinstance(tables, list)
    assert len(tables) == 1

    table = tables[0]
    assert isinstance(table, DataTable)
    assert table.name == "test"
    assert table.engine == "test_sqlite"
    assert len(table.columns) == 2
    assert table.columns[0].name == "id"
    assert table.columns[0].type == "integer"
    assert table.columns[1].name == "name"
    assert table.columns[1].type == "string"


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_engine_get_tables(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    """Test DuckDBEngine get_tables method."""
    engine = DuckDBEngine(duckdb_connection, engine_name="test_duckdb")
    tables = engine.get_tables()

    assert isinstance(tables, list)
    assert len(tables) == 1

    table = tables[0]
    assert isinstance(table, DataTable)
    assert table.name == "memory.main.test"
    assert table.engine == "test_duckdb"
    assert table.source_type == "connection"
    assert len(table.columns) == 2
    assert table.columns[0].name == "id"
    assert table.columns[0].type == "integer"
    assert table.columns[1].name == "name"
    assert table.columns[1].type == "string"


@pytest.mark.skipif(
    not HAS_DUCKDB or not HAS_SQLALCHEMY,
    reason="Duckdb and sqlalchemy not installed",
)
def test_engine_name_initialization() -> None:
    """Test engine name initialization."""
    import duckdb
    import sqlalchemy as sa

    duckdb_conn = duckdb.connect(":memory:")
    sqlite_engine = sa.create_engine("sqlite:///:memory:")

    duck_engine = DuckDBEngine(duckdb_conn, engine_name="my_duck")
    sql_engine = SQLAlchemyEngine(sqlite_engine, engine_name="my_sql")

    assert duck_engine._engine_name == "my_duck"
    assert sql_engine._engine_name == "my_sql"

    # Test default names
    duck_engine_default = DuckDBEngine(duckdb_conn)
    sql_engine_default = SQLAlchemyEngine(sqlite_engine)

    assert duck_engine_default._engine_name is None
    assert sql_engine_default._engine_name is None

    duckdb_conn.close()
