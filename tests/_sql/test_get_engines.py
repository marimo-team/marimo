from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from marimo._data.models import DataSourceConnection
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines import DuckDBEngine, SQLAlchemyEngine
from marimo._sql.get_engines import (
    engine_to_data_source_connection,
    get_engines_from_variables,
)

HAS_SQLALCHEMY = DependencyManager.sqlalchemy.has()
HAS_DUCKDB = DependencyManager.duckdb.has()


def test_engine_to_data_source_connection():
    # Test with DuckDB engine
    duckdb_engine = DuckDBEngine(None)
    connection = engine_to_data_source_connection("my_duckdb", duckdb_engine)
    assert isinstance(connection, DataSourceConnection)
    assert connection.source == "duckdb"
    assert connection.dialect == "duckdb"
    assert connection.name == "my_duckdb"
    assert connection.display_name == "duckdb (my_duckdb)"

    # Test with SQLAlchemy engine
    mock_sqlalchemy_engine = MagicMock()
    mock_sqlalchemy_engine.dialect.name = "postgresql"
    sqlalchemy_engine = SQLAlchemyEngine(mock_sqlalchemy_engine)
    connection = engine_to_data_source_connection(
        "my_postgres", sqlalchemy_engine
    )
    assert isinstance(connection, DataSourceConnection)
    assert connection.source == "postgresql"
    assert connection.dialect == "postgresql"
    assert connection.name == "my_postgres"
    assert connection.display_name == "postgresql (my_postgres)"


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_get_engines_from_variables_duckdb():
    import duckdb

    mock_duckdb_conn = MagicMock(spec=duckdb.DuckDBPyConnection)
    variables: list[tuple[str, object]] = [("duckdb_conn", mock_duckdb_conn)]

    engines = get_engines_from_variables(variables)
    assert len(engines) == 1
    var_name, engine = engines[0]
    assert var_name == "duckdb_conn"
    assert isinstance(engine, DuckDBEngine)


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_get_engines_from_variables_sqlalchemy():
    import sqlalchemy as sa

    mock_sqlalchemy_engine = MagicMock(spec=sa.Engine)
    variables: list[tuple[str, object]] = [
        ("sa_engine", mock_sqlalchemy_engine)
    ]

    engines = get_engines_from_variables(variables)
    assert len(engines) == 1
    var_name, engine = engines[0]
    assert var_name == "sa_engine"
    assert isinstance(engine, SQLAlchemyEngine)


def test_get_engines_from_variables_mixed():
    variables: list[tuple[str, object]] = [
        ("not_an_engine", "some string"),
        ("another_not_engine", 42),
    ]

    engines = get_engines_from_variables(variables)
    assert len(engines) == 0


@pytest.mark.skipif(
    not (HAS_SQLALCHEMY and HAS_DUCKDB),
    reason="SQLAlchemy or DuckDB not installed",
)
def test_get_engines_from_variables_multiple():
    import duckdb
    import sqlalchemy as sa

    mock_sqlalchemy_engine = MagicMock(spec=sa.Engine)
    mock_duckdb_conn = MagicMock(spec=duckdb.DuckDBPyConnection)

    variables: list[tuple[str, object]] = [
        ("sa_engine", mock_sqlalchemy_engine),
        ("duckdb_conn", mock_duckdb_conn),
        ("not_an_engine", "some string"),
    ]

    engines = get_engines_from_variables(variables)
    assert len(engines) == 2

    # Check SQLAlchemy engine
    sa_var_name, _sa_engine = next(
        (name, eng)
        for name, eng in engines
        if isinstance(eng, SQLAlchemyEngine)
    )
    assert sa_var_name == "sa_engine"

    # Check DuckDB engine
    duckdb_var_name, _duckdb_engine = next(
        (name, eng) for name, eng in engines if isinstance(eng, DuckDBEngine)
    )
    assert duckdb_var_name == "duckdb_conn"
