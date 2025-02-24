"""General tests for the SQL engines."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines import (
    DuckDBEngine,
    SQLAlchemyEngine,
    raise_df_import_error,
)

HAS_DUCKDB = DependencyManager.duckdb.has()
HAS_SQLALCHEMY = DependencyManager.sqlalchemy.has()
HAS_PANDAS = DependencyManager.pandas.has()


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
