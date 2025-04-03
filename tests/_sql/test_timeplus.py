from __future__ import annotations

import pytest

from marimo._data.models import DataSourceConnection
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.clickhouse import ClickhouseEmbedded, ClickhouseServer
from marimo._sql.get_engines import engine_to_data_source_connection
from marimo._sql.sql import sql

HAS_CHDB = DependencyManager.chdb.has() and DependencyManager.pandas.has()
HAS_CLICKHOUSE_CONNECT = (
    DependencyManager.clickhouse_connect.has()
    and DependencyManager.pandas.has()
)


@pytest.mark.skipif(
    not HAS_CLICKHOUSE_CONNECT, reason="Clickhouse and Pandas not installed"
)
def test_clickhouse_server_creation() -> None:
    engine = ClickhouseServer(None)
    connection = engine_to_data_source_connection("clickhouse", engine=engine)
    assert isinstance(connection, DataSourceConnection)

    assert connection.databases == []
    # assert connection.default_database == "default"
    # assert connection.default_schema == "default"
    assert connection.display_name == "clickhouse (clickhouse)"
    assert connection.dialect == "clickhouse"
    assert connection.name == "clickhouse"
    assert connection.source == "clickhouse"


@pytest.mark.skipif(not HAS_CHDB, reason="chdb and pandas not installed")
def test_clickhouse_embedded_creation() -> None:
    import chdb

    chdb_conn = chdb.connect(":memory:")
    engine = ClickhouseEmbedded(
        connection=chdb_conn, engine_name="clickhouse_embedded"
    )
    assert engine.dialect == "clickhouse"
    assert engine._engine_name == "clickhouse_embedded"

    connection = engine_to_data_source_connection("clickhouse", engine=engine)
    assert isinstance(connection, DataSourceConnection)

    assert connection.databases == []
    # assert connection.default_database == "default"
    # assert connection.default_schema == "default"
    assert connection.display_name == "clickhouse (clickhouse)"
    assert connection.dialect == "clickhouse"
    assert connection.name == "clickhouse"
    assert connection.source == "clickhouse"

    chdb_conn.close()


@pytest.mark.skipif(not HAS_CHDB, reason="chdb and pandas not installed")
@pytest.mark.xfail(reason="Flaky test")
def test_clickhouse_execute() -> None:
    import chdb
    import pandas as pd

    chdb_conn = chdb.connect(":memory:")

    sql(
        "CREATE TABLE test (id Int32, name String) ENGINE = Memory",
        engine=chdb_conn,
    )
    sql(
        "INSERT INTO test VALUES (1, 'Alice'), (2, 'Bob')",
        engine=chdb_conn,
    )
    result = sql("SELECT * FROM test", engine=chdb_conn)

    assert isinstance(result, pd.DataFrame)
    expected = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
    assert result.equals(expected)

    chdb_conn.close()
