from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from marimo._data.models import (
    Database,
    DataSourceConnection,
    DataTableColumn,
    Schema,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.clickhouse import ClickhouseEmbedded
from marimo._sql.engines.dbapi import DBAPIEngine
from marimo._sql.engines.duckdb import (
    INTERNAL_DUCKDB_ENGINE,
    DuckDBEngine,
)
from marimo._sql.engines.ibis import IbisEngine
from marimo._sql.engines.sqlalchemy import SQLAlchemyEngine
from marimo._sql.get_engines import (
    engine_to_data_source_connection,
    get_engines_from_variables,
)
from marimo._sql.sql import sql
from marimo._types.ids import VariableName

HAS_SQLALCHEMY = DependencyManager.sqlalchemy.has()
HAS_IBIS = DependencyManager.ibis.has()
HAS_DUCKDB = DependencyManager.duckdb.has()
HAS_CLICKHOUSE = DependencyManager.chdb.has()


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_engine_to_data_source_connection() -> None:
    import sqlalchemy  # noqa: F401, needed for patching sqlalchemy.inspect

    # Test with DuckDB engine
    duckdb_engine = DuckDBEngine(None)
    connection = engine_to_data_source_connection(
        VariableName("my_duckdb"), duckdb_engine
    )
    assert isinstance(connection, DataSourceConnection)
    assert connection.source == "duckdb"
    assert connection.dialect == "duckdb"
    assert connection.name == "my_duckdb"
    assert connection.display_name == "duckdb (my_duckdb)"
    assert connection.default_database == "memory"
    assert connection.default_schema == "main"
    assert connection.databases == []

    # Test with ClickhouseEmbedded engine
    clickhouse_engine = ClickhouseEmbedded(None)
    connection = engine_to_data_source_connection(
        "my_clickhouse", clickhouse_engine
    )
    assert isinstance(connection, DataSourceConnection)
    assert connection.source == "clickhouse"
    assert connection.dialect == "clickhouse"
    assert connection.name == "my_clickhouse"
    assert connection.display_name == "clickhouse (my_clickhouse)"
    # assert connection.default_database == "default"
    # assert connection.default_schema == "default"
    assert connection.databases == []

    # Test with SQLAlchemy engine
    mock_sqlalchemy_engine = MagicMock()
    mock_sqlalchemy_engine.dialect.name = "postgresql"

    with patch("sqlalchemy.inspect", return_value=MagicMock()):
        sqlalchemy_engine = SQLAlchemyEngine(mock_sqlalchemy_engine)

    connection = engine_to_data_source_connection(
        "my_postgres", sqlalchemy_engine
    )
    assert isinstance(connection, DataSourceConnection)
    assert connection.source == "sqlalchemy"
    assert connection.dialect == "postgresql"
    assert connection.name == "my_postgres"
    assert connection.display_name == "postgresql (my_postgres)"

    # Test with Ibis engine
    var_name = "my_ibis"
    backend_name = "duckdb"
    backend_class = MagicMock
    mock_ibis_backend = MagicMock()
    mock_ibis_backend.dialect = backend_class
    mock_ibis_backend.dialect.classes = {backend_name: backend_class}

    ibis_engine = IbisEngine(mock_ibis_backend)
    connection = engine_to_data_source_connection(var_name, ibis_engine)
    assert isinstance(connection, DataSourceConnection)
    assert connection.source == "ibis"
    assert connection.dialect == backend_name
    assert connection.name == var_name
    assert connection.display_name == f"{backend_name} ({var_name})"


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


@pytest.mark.skipif(not HAS_CLICKHOUSE, reason="Clickhouse not installed")
def test_get_engines_from_variables_clickhouse():
    import chdb

    mock_clickhouse_conn = MagicMock(spec=chdb.state.sqlitelike.Connection)
    variables: list[tuple[str, object]] = [
        ("clickhouse_conn", mock_clickhouse_conn)
    ]

    engines = get_engines_from_variables(variables)
    assert len(engines) == 1
    var_name, engine = engines[0]
    assert var_name == "clickhouse_conn"
    assert isinstance(engine, ClickhouseEmbedded)


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_get_engines_from_variables_sqlalchemy() -> None:
    import sqlalchemy as sa

    sqlalchemy_engine = sa.create_engine("sqlite:///:memory:")
    variables: list[tuple[str, object]] = [("sa_engine", sqlalchemy_engine)]

    engines = get_engines_from_variables(variables)

    assert len(engines) == 1
    var_name, engine = engines[0]
    assert var_name == "sa_engine"
    assert isinstance(engine, SQLAlchemyEngine)


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_get_engines_from_variables_ibis() -> None:
    import ibis

    ibis_backend = ibis.duckdb.connect()
    variables: list[tuple[str, object]] = [("ibis_backend", ibis_backend)]

    engines = get_engines_from_variables(variables)

    assert len(engines) == 1
    var_name, engine = engines[0]
    assert var_name == "ibis_backend"
    assert isinstance(engine, IbisEngine)


def test_get_engines_from_variables_mixed():
    variables: list[tuple[str, object]] = [
        ("not_an_engine", "some string"),
        ("another_not_engine", 42),
    ]

    engines = get_engines_from_variables(variables)
    assert len(engines) == 0


@pytest.mark.skipif(
    not (HAS_SQLALCHEMY and HAS_DUCKDB and HAS_CLICKHOUSE and HAS_IBIS),
    reason="SQLAlchemy, Clickhouse, Ibis, or DuckDB not installed",
)
def test_get_engines_from_variables_multiple():
    import chdb
    import duckdb
    import ibis
    import sqlalchemy as sa

    mock_duckdb_conn = MagicMock(spec=duckdb.DuckDBPyConnection)
    mock_clickhouse = MagicMock(spec=chdb.state.sqlitelike.Connection)
    sqlalchemy_engine = sa.create_engine("sqlite:///:memory:")
    ibis_backend = ibis.duckdb.connect()

    variables: list[tuple[str, object]] = [
        ("sa_engine", sqlalchemy_engine),
        ("duckdb_conn", mock_duckdb_conn),
        ("clickhouse_conn", mock_clickhouse),
        ("ibis_backend", ibis_backend),
        ("not_an_engine", "some string"),
    ]

    engines = get_engines_from_variables(variables)

    assert len(engines) == 4

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

    # Check Clickhouse engine
    ch_var_name, _ch_engine = next(
        (name, eng)
        for name, eng in engines
        if isinstance(eng, ClickhouseEmbedded)
    )
    assert ch_var_name == "clickhouse_conn"

    # Check Clickhouse engine
    ibis_var_name, _ibis_engine = next(
        (name, eng) for name, eng in engines if isinstance(eng, IbisEngine)
    )
    assert ibis_var_name == "ibis_backend"


def test_get_engines_dbapi():
    import sqlite3

    mock_sqlite_conn = MagicMock(spec=sqlite3.Connection)
    variables: list[tuple[str, object]] = [("sqlite_conn", mock_sqlite_conn)]

    engines = get_engines_from_variables(variables)
    assert len(engines) == 1
    var_name, engine = engines[0]
    assert var_name == "sqlite_conn"
    assert isinstance(engine, DBAPIEngine)


def test_get_engines_dbapi_databases():
    import sqlite3

    with sqlite3.connect(":memory:") as conn:
        engine = DBAPIEngine(conn)
        connection = engine_to_data_source_connection(
            VariableName("sqlite_conn"), engine
        )
        assert connection.databases == []
        assert connection.dialect == "sql"


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_get_engines_duckdb_databases() -> None:
    duckdb_engine = DuckDBEngine(None)

    # Test display name when the name is DEFAULT_ENGINE_NAME
    connection = engine_to_data_source_connection(
        INTERNAL_DUCKDB_ENGINE, duckdb_engine
    )
    assert connection.display_name == "duckdb (In-Memory)"

    connection = engine_to_data_source_connection(
        VariableName("my_duckdb"), duckdb_engine
    )
    assert isinstance(connection, DataSourceConnection)

    assert connection.source == "duckdb"
    assert connection.dialect == "duckdb"
    assert connection.name == "my_duckdb"
    assert connection.display_name == "duckdb (my_duckdb)"
    assert connection.default_database == "memory"
    assert connection.default_schema == "main"

    sql("CREATE TABLE test_table (id INTEGER);")

    # Reload the connection to get the new table
    connection = engine_to_data_source_connection(
        VariableName("my_duckdb"), duckdb_engine
    )

    assert len(connection.databases) == 1
    database = connection.databases[0]
    assert database.name == "memory"
    assert len(database.schemas) == 1
    schema = database.schemas[0]
    assert schema.name == "main"
    assert len(schema.tables) == 1
    table = schema.tables[0]
    assert table.name == "test_table"
    assert table.columns == [
        DataTableColumn(
            name="id",
            type="integer",
            external_type="INTEGER",
            sample_values=[],
        )
    ]
    sql("DROP TABLE test_table;")


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_get_engines_sqlalchemy_databases() -> None:
    import sqlalchemy as sa

    sqlalchemy_engine = sa.create_engine("sqlite:///:memory:")
    engine = SQLAlchemyEngine(sqlalchemy_engine)

    connection = engine_to_data_source_connection(
        VariableName("sqlite"), engine
    )
    assert isinstance(connection, DataSourceConnection)

    assert connection.source == "sqlalchemy"
    assert connection.dialect == "sqlite"
    assert connection.name == "sqlite"
    assert connection.display_name == "sqlite (sqlite)"
    assert connection.default_database == ":memory:"
    assert connection.default_schema == "main"

    assert connection.databases == [
        Database(
            name=":memory:",
            dialect="sqlite",
            schemas=[Schema(name="main", tables=[])],
        )
    ]


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_get_engines_ibis_databases() -> None:
    import ibis

    ibis_backend = ibis.duckdb.connect()
    engine = IbisEngine(ibis_backend)

    connection = engine_to_data_source_connection(
        VariableName("my_ibis"), engine
    )
    assert isinstance(connection, DataSourceConnection)

    assert connection.source == "ibis"
    assert connection.dialect == "duckdb"
    assert connection.name == "my_ibis"
    assert connection.display_name == "duckdb (my_ibis)"
    assert connection.default_database == "memory"
    assert connection.default_schema == "main"

    assert connection.databases == [
        Database(
            name="memory",
            dialect="duckdb",
            schemas=[Schema(name="main", tables=[])],
        )
    ]


@pytest.mark.skipif(not HAS_CLICKHOUSE, reason="Clickhouse not installed")
def test_get_engines_clickhouse() -> None:
    import chdb

    clickhouse_conn = chdb.connect(":memory:")
    engine = ClickhouseEmbedded(
        clickhouse_conn, engine_name=VariableName("clickhouse")
    )
    variable_name = VariableName("clickhouse_conn")

    connection = engine_to_data_source_connection(variable_name, engine)
    assert isinstance(connection, DataSourceConnection)

    assert connection.source == "clickhouse"
    assert connection.dialect == "clickhouse"
    assert connection.name == variable_name
    assert connection.display_name == f"clickhouse ({variable_name})"
    # assert connection.default_database == "default"
    # assert connection.default_schema == "default"
    assert connection.databases == []
