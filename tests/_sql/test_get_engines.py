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
from marimo._sql.engines import (
    INTERNAL_DUCKDB_ENGINE,
    ClickhouseEmbedded,
    DuckDBEngine,
    SQLAlchemyEngine,
)
from marimo._sql.get_engines import (
    engine_to_data_source_connection,
    get_engines_from_variables,
)
from marimo._sql.sql import sql

HAS_SQLALCHEMY = DependencyManager.sqlalchemy.has()
HAS_DUCKDB = DependencyManager.duckdb.has()
HAS_CLICKHOUSE = DependencyManager.chdb.has()


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_engine_to_data_source_connection() -> None:
    import sqlalchemy  # noqa: F401, needed for patching sqlalchemy.inspect

    # Test with DuckDB engine
    duckdb_engine = DuckDBEngine(None)
    connection = engine_to_data_source_connection("my_duckdb", duckdb_engine)
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


def test_get_engines_from_variables_mixed():
    variables: list[tuple[str, object]] = [
        ("not_an_engine", "some string"),
        ("another_not_engine", 42),
    ]

    engines = get_engines_from_variables(variables)
    assert len(engines) == 0


@pytest.mark.skipif(
    not (HAS_SQLALCHEMY and HAS_DUCKDB and HAS_CLICKHOUSE),
    reason="SQLAlchemy or DuckDB not installed",
)
def test_get_engines_from_variables_multiple():
    import chdb
    import duckdb
    import sqlalchemy as sa

    mock_duckdb_conn = MagicMock(spec=duckdb.DuckDBPyConnection)
    mock_clickhouse = MagicMock(spec=chdb.state.sqlitelike.Connection)
    sqlalchemy_engine = sa.create_engine("sqlite:///:memory:")

    variables: list[tuple[str, object]] = [
        ("sa_engine", sqlalchemy_engine),
        ("duckdb_conn", mock_duckdb_conn),
        ("clickhouse_conn", mock_clickhouse),
        ("not_an_engine", "some string"),
    ]

    engines = get_engines_from_variables(variables)

    assert len(engines) == 3

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


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_get_engines_duckdb_databases() -> None:
    duckdb_engine = DuckDBEngine(None)

    # Test display name when the name is DEFAULT_ENGINE_NAME
    connection = engine_to_data_source_connection(
        INTERNAL_DUCKDB_ENGINE, duckdb_engine
    )
    assert connection.display_name == "duckdb (In-Memory)"

    connection = engine_to_data_source_connection("my_duckdb", duckdb_engine)
    assert isinstance(connection, DataSourceConnection)

    assert connection.source == "duckdb"
    assert connection.dialect == "duckdb"
    assert connection.name == "my_duckdb"
    assert connection.display_name == "duckdb (my_duckdb)"
    assert connection.default_database == "memory"
    assert connection.default_schema == "main"

    sql("CREATE TABLE test_table (id INTEGER);")

    # Reload the connection to get the new table
    connection = engine_to_data_source_connection("my_duckdb", duckdb_engine)

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

    connection = engine_to_data_source_connection("sqlite", engine)
    assert isinstance(connection, DataSourceConnection)

    assert connection.source == "sqlite"
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


@pytest.mark.skipif(not HAS_CLICKHOUSE, reason="Clickhouse not installed")
def test_get_engines_clickhouse() -> None:
    import chdb

    clickhouse_conn = chdb.connect(":memory:")
    engine = ClickhouseEmbedded(clickhouse_conn, engine_name="clickhouse")
    variable_name = "clickhouse_conn"

    connection = engine_to_data_source_connection(variable_name, engine)
    assert isinstance(connection, DataSourceConnection)

    assert connection.source == "clickhouse"
    assert connection.dialect == "clickhouse"
    assert connection.name == variable_name
    assert connection.display_name == f"clickhouse ({variable_name})"
    # assert connection.default_database == "default"
    # assert connection.default_schema == "default"
    assert connection.databases == []
