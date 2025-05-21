from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from marimo._config.config import SqlOutputType
from marimo._data.models import DataSourceConnection
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.clickhouse import ClickhouseEmbedded, ClickhouseServer
from marimo._sql.engines.types import EngineCatalog, QueryEngine
from marimo._sql.get_engines import engine_to_data_source_connection
from marimo._sql.sql import sql

HAS_CHDB = DependencyManager.chdb.has()
HAS_POLARS = DependencyManager.polars.has()
HAS_PANDAS = DependencyManager.pandas.has()
HAS_CLICKHOUSE_CONNECT = DependencyManager.clickhouse_connect.has()


@pytest.mark.skipif(
    not HAS_CLICKHOUSE_CONNECT, reason="Clickhouse connect not installed"
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


@pytest.mark.skipif(not HAS_CHDB, reason="chdb not installed")
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

    assert isinstance(engine, ClickhouseEmbedded)
    assert isinstance(engine, EngineCatalog)
    assert isinstance(engine, QueryEngine)

    chdb_conn.close()


@pytest.mark.skipif(
    not HAS_CHDB and not HAS_POLARS, reason="chdb and polars not installed"
)
def test_clickhouse_embedded_execute() -> None:
    import chdb
    import polars as pl

    chdb_conn = None
    try:
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

        assert isinstance(result, pl.DataFrame)
        expected = pl.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
        assert result.equals(expected)
    finally:
        if chdb_conn is not None:
            chdb_conn.close()


@pytest.mark.skipif(
    not HAS_CHDB and not HAS_POLARS and not HAS_PANDAS,
    reason="chdb, polars, and pandas not installed",
)
def test_clickhouse_emdbedded_connection_based_output_formats() -> None:
    import chdb
    import pandas as pd
    import polars as pl

    # Test different output formats
    output_formats: tuple[SqlOutputType, Any, Any] = [
        ("native", None, None),
        ("polars", pl.DataFrame, pl.DataFrame({"1": [1], "2": [2]})),
        ("lazy-polars", pl.LazyFrame, None),
        ("pandas", pd.DataFrame, pd.DataFrame({"1": [1], "2": [2]})),
        ("auto", pl.DataFrame, pl.DataFrame({"1": [1]})),
    ]

    for format_name, expected_type, expected_result in output_formats:
        with mock.patch.object(
            ClickhouseEmbedded, "sql_output_format", return_value=format_name
        ):
            chdb_conn = None
            try:
                chdb_conn = chdb.connect(":memory:")
                query = "SELECT 1, 2" if format_name != "auto" else "SELECT 1"
                if format_name == "lazy-polars":
                    query = "SELECT 1, 2 FROM generate_series(1, 2)"

                result = sql(query, engine=chdb_conn)

                if format_name == "native":
                    assert result is None
                else:
                    assert isinstance(result, expected_type)
                    if expected_result is not None:
                        assert result.equals(expected_result)
                    if format_name == "lazy-polars":
                        assert len(result.collect()) == 2
            finally:
                if chdb_conn is not None:
                    chdb_conn.close()

    # Test auto when polars not available
    with (
        mock.patch.object(
            ClickhouseEmbedded, "sql_output_format", return_value="auto"
        ),
        mock.patch.object(DependencyManager.polars, "has", return_value=False),
    ):
        chdb_conn = None
        try:
            chdb_conn = chdb.connect(":memory:")
            result = sql("SELECT 1", engine=chdb_conn)
            assert isinstance(result, pd.DataFrame)
            assert result.equals(pd.DataFrame({"1": [1]}))
        finally:
            if chdb_conn is not None:
                chdb_conn.close()
