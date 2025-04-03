from __future__ import annotations

import pytest

from marimo._data.models import DataSourceConnection
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.timeplus import TimeplusServer
from marimo._sql.get_engines import engine_to_data_source_connection
from marimo._sql.sql import sql

HAS_TIMEPLUS_CONNECT = (
    DependencyManager.timeplus_connect.has() and DependencyManager.pandas.has()
)


@pytest.mark.skipif(
    not HAS_TIMEPLUS_CONNECT, reason="Timeplus and Pandas not installed"
)
def test_timeplus_server_creation() -> None:
    engine = TimeplusServer(None)
    connection = engine_to_data_source_connection("timeplus", engine=engine)
    assert isinstance(connection, DataSourceConnection)

    assert connection.databases == []
    # assert connection.default_database == "default"
    # assert connection.default_schema == "default"
    assert connection.display_name == "timeplus (timeplus)"
    assert connection.dialect == "timeplus"
    assert connection.name == "timeplus"
    assert connection.source == "timeplus"


@pytest.mark.skipif(
    not HAS_TIMEPLUS_CONNECT, reason="Timeplus and pandas not installed"
)
@pytest.mark.xfail(reason="Flaky test")
def test_timeplus_execute() -> None:
    import pandas as pd

    engine = TimeplusServer(None)
    connection = engine_to_data_source_connection("timeplus", engine=engine)
    assert isinstance(connection, DataSourceConnection)

    sql(
        "CREATE STREAM test (id int32, name string) ENGINE = Memory",
        engine=connection,
    )
    sql(
        "INSERT INTO test VALUES (1, 'Alice'), (2, 'Bob')",
        engine=connection,
    )
    result = sql("SELECT * FROM test", engine=connection)

    assert isinstance(result, pd.DataFrame)
    expected = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
    assert result.equals(expected)
