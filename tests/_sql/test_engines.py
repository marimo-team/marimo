"""Tests for SQL engines."""

from __future__ import annotations

from typing import TYPE_CHECKING, Generator
from unittest.mock import MagicMock

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines import (
    DuckDBEngine,
    SQLAlchemyEngine,
    raise_df_import_error,
)
from marimo._sql.sql import _execute_query

HAS_DUCKDB = DependencyManager.duckdb.has()
HAS_SQLALCHEMY = DependencyManager.sqlalchemy.has()
HAS_POLARS = DependencyManager.polars.has()

if TYPE_CHECKING:
    import duckdb
    import sqlalchemy as sa


@pytest.fixture
def sqlite_engine() -> sa.Engine:
    """Create a temporary SQLite database for testing."""

    import sqlalchemy as sa
    from sqlalchemy import text

    engine = sa.create_engine("sqlite:///:memory:")
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


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_engine_execute(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    """Test DuckDBEngine execute with both connection and no connection."""
    import pandas as pd
    import polars as pl

    # Test with explicit connection
    engine = DuckDBEngine(duckdb_connection)
    result = _execute_query("SELECT * FROM test ORDER BY id", engine)
    assert isinstance(result, (pd.DataFrame, pl.DataFrame))
    assert len(result) == 3


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_engine_execute(sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine execute."""
    import pandas as pd
    import polars as pl

    engine = SQLAlchemyEngine(sqlite_engine)
    result = _execute_query("SELECT * FROM test ORDER BY id", engine)
    assert isinstance(result, (pd.DataFrame, pl.DataFrame))
    assert len(result) == 3


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
