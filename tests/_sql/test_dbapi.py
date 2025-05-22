# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

from marimo._sql.engines.dbapi import DBAPIEngine
from marimo._sql.engines.types import EngineCatalog, QueryEngine


@pytest.fixture
def sqlite_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE test (
            id INTEGER PRIMARY KEY,
            name TEXT,
            value REAL
        )
    """)
    conn.execute("""
        INSERT INTO test (name, value) VALUES
        ('a', 1.0),
        ('b', 2.0),
        ('c', 3.0)
    """)
    return conn


@pytest.fixture
def dbapi_engine(sqlite_connection: sqlite3.Connection) -> DBAPIEngine:
    return DBAPIEngine(connection=sqlite_connection)


def test_source(dbapi_engine: DBAPIEngine) -> None:
    assert dbapi_engine.source == "dbapi"


def test_dialect(dbapi_engine: DBAPIEngine) -> None:
    assert dbapi_engine.dialect == "sql"


def test_is_compatible() -> None:
    # Test with sqlite3 connection
    conn = sqlite3.connect(":memory:")
    assert DBAPIEngine.is_compatible(conn)
    conn.close()

    # Test with non-DBAPI object
    assert not DBAPIEngine.is_compatible("not a connection")
    assert not DBAPIEngine.is_compatible(None)

    engine = DBAPIEngine(conn)
    assert isinstance(engine, DBAPIEngine)
    assert isinstance(engine, QueryEngine)
    assert not isinstance(engine, EngineCatalog)


def test_execute_native(dbapi_engine: DBAPIEngine) -> None:
    with patch.object(
        dbapi_engine, "sql_output_format", return_value="native"
    ):
        result = dbapi_engine.execute("SELECT * FROM test")
        assert isinstance(result, sqlite3.Cursor)
        assert result.fetchall() == [
            (1, "a", 1.0),
            (2, "b", 2.0),
            (3, "c", 3.0),
        ]


def test_execute_pandas(dbapi_engine: DBAPIEngine) -> None:
    pd = pytest.importorskip("pandas")
    with patch.object(
        dbapi_engine, "sql_output_format", return_value="pandas"
    ):
        result = dbapi_engine.execute("SELECT * FROM test")
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["id", "name", "value"]
        assert len(result) == 3
    assert result.iloc[0].to_dict() == {"id": 1, "name": "a", "value": 1.0}


def test_execute_polars(dbapi_engine: DBAPIEngine) -> None:
    pl = pytest.importorskip("polars")
    with patch.object(
        dbapi_engine, "sql_output_format", return_value="polars"
    ):
        result = dbapi_engine.execute("SELECT * FROM test")
        assert isinstance(result, pl.DataFrame)
        assert result.columns == ["id", "name", "value"]
        assert len(result) == 3
        assert result.row(0) == (1, "a", 1.0)


def test_execute_lazy_polars(dbapi_engine: DBAPIEngine) -> None:
    pl = pytest.importorskip("polars")
    with patch.object(
        dbapi_engine, "sql_output_format", return_value="lazy-polars"
    ):
        result = dbapi_engine.execute("SELECT * FROM test")
        assert isinstance(result, pl.LazyFrame)
        result = result.collect()
        assert result.columns == ["id", "name", "value"]
        assert result.row(0) == (1, "a", 1.0)


def test_execute_no_results(dbapi_engine: DBAPIEngine) -> None:
    result = dbapi_engine.execute("CREATE TABLE empty (id INTEGER)")
    assert result is None


def test_execute_error(dbapi_engine: DBAPIEngine) -> None:
    with pytest.raises(sqlite3.OperationalError):
        dbapi_engine.execute("SELECT * FROM nonexistent")


def test_execute_transaction(dbapi_engine: DBAPIEngine) -> None:
    pytest.importorskip("pandas")

    # Test that transaction is committed
    with patch.object(
        dbapi_engine, "sql_output_format", return_value="pandas"
    ):
        dbapi_engine.execute(
            "INSERT INTO test (name, value) VALUES ('d', 4.0)"
        )
        result = dbapi_engine.execute("SELECT * FROM test")
        assert len(result) == 4
        assert result.iloc[3].to_dict() == {"id": 4, "name": "d", "value": 4.0}


def test_execute_with_parameters(dbapi_engine: DBAPIEngine) -> None:
    pytest.importorskip("pandas")

    with patch.object(
        dbapi_engine, "sql_output_format", return_value="pandas"
    ):
        result = dbapi_engine.execute(
            "SELECT * FROM test WHERE name = ?", ["a"]
        )
        assert len(result) == 1
        assert result.iloc[0].to_dict() == {"id": 1, "name": "a", "value": 1.0}
