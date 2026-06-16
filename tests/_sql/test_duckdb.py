# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import sys
from copy import deepcopy
from typing import TYPE_CHECKING, Any
from unittest import mock

import pytest

from marimo._data.models import Database, DataTable, DataTableColumn, Schema
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.duckdb import DuckDBEngine
from marimo._sql.engines.types import EngineCatalog, QueryEngine
from marimo._sql.sql import sql
from marimo._types.ids import VariableName

HAS_DUCKDB = DependencyManager.duckdb.has()
HAS_PANDAS = DependencyManager.pandas.has()
HAS_POLARS = DependencyManager.polars.has()

if TYPE_CHECKING:
    from collections.abc import Generator

    import duckdb


@pytest.fixture
def duckdb_connection() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Create a DuckDB connection for testing."""

    import duckdb

    conn = duckdb.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE test (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255)
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
    conn.execute("DROP TABLE test")
    conn.close()


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_engine_dialect() -> None:
    """Test DuckDBEngine dialect property."""
    engine = DuckDBEngine(None, engine_name=None)
    assert engine.dialect == "duckdb"


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_engine_is_instance() -> None:
    """Test DuckDBEngine is an instance of the correct types."""
    engine = DuckDBEngine(None, engine_name=None)
    assert isinstance(engine, DuckDBEngine)
    assert isinstance(engine, EngineCatalog)
    assert isinstance(engine, QueryEngine)


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
    engine = DuckDBEngine(duckdb_connection, engine_name=None)
    result = engine.execute("SELECT * FROM test ORDER BY id")
    assert isinstance(result, (pd.DataFrame, pl.DataFrame))
    assert len(result) == 4


expected_databases_with_conn = [
    Database(
        name="memory",
        dialect="duckdb",
        engine=VariableName("test_duckdb"),
        children=[
            Schema(
                name="main",
                tables=[
                    DataTable(
                        name="test",
                        source="memory",
                        source_type="connection",
                        num_rows=None,
                        num_columns=2,
                        variable_name=None,
                        engine=VariableName("test_duckdb"),
                        columns=[
                            DataTableColumn(
                                name="id",
                                type="integer",
                                external_type="INTEGER",
                                sample_values=[],
                            ),
                            DataTableColumn(
                                name="name",
                                type="string",
                                external_type="VARCHAR",
                                sample_values=[],
                            ),
                        ],
                    )
                ],
            )
        ],
    )
]


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_engine_get_databases(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    """Test DuckDBEngine get_databases method."""

    engine = DuckDBEngine(
        duckdb_connection, engine_name=VariableName("test_duckdb")
    )
    databases = engine.get_databases(
        include_schemas=True, include_tables=True, include_table_details=True
    )

    assert databases == expected_databases_with_conn


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_engine_get_catalog_children(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    """DuckDB serves lazy catalog expansion from its full-tree loader."""
    engine = DuckDBEngine(
        duckdb_connection, engine_name=VariableName("test_duckdb")
    )

    root_children = engine.get_catalog_children(
        database="memory",
        catalog_path=[],
        include_table_details=False,
    )
    schema_children = engine.get_catalog_children(
        database="memory",
        catalog_path=["main"],
        include_table_details=False,
    )
    expected_schema = expected_databases_with_conn[0].children[0]
    assert isinstance(expected_schema, Schema)

    assert root_children == expected_databases_with_conn[0].children
    assert schema_children == expected_schema.tables


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_engine_get_databases_no_conn() -> None:
    """Test DuckDBEngine get_databases method."""
    engine = DuckDBEngine(None, engine_name=None)
    initial_databases = engine.get_databases(
        include_schemas=False,
        include_table_details=False,
        include_tables=False,
    )
    assert initial_databases == [
        Database(name="memory", dialect="duckdb", children=None)
    ]
    assert engine.get_default_database() == "memory"
    assert engine.get_default_schema() == "main"

    engine.execute(
        "CREATE TABLE test (id INTEGER PRIMARY KEY, name VARCHAR(255))"
    )
    engine.execute(
        """
        INSERT INTO test VALUES
        (1, 'Alice'),
        (2, 'Bob'),
        (3, 'Charlie');
        """
    )
    databases = engine.get_databases(
        include_schemas=True, include_tables=True, include_table_details=True
    )

    expected_databases = deepcopy(expected_databases_with_conn)
    expected_databases[0].engine = None
    expected_databases[0].children[0].tables[0].engine = None
    expected_databases[0].children[0].tables[0].source_type = "duckdb"
    expected_databases[0].children[0].tables[0].source = "memory"

    assert databases == expected_databases

    engine.execute("DROP TABLE test")


@pytest.mark.skipif(not HAS_DUCKDB, reason="duckdb not installed")
def test_get_current_database_schema() -> None:
    import duckdb

    engine = duckdb.connect(":memory:")
    duckdb_engine = DuckDBEngine(
        engine, engine_name=VariableName("test_duckdb")
    )

    assert duckdb_engine.get_default_database() == "memory"
    assert duckdb_engine.get_default_schema() == "main"

    sql("CREATE SCHEMA test_schema;", engine=engine)
    sql("CREATE TABLE test_schema.test_table (id INTEGER);", engine=engine)
    sql("USE test_schema;", engine=engine)

    assert duckdb_engine.get_default_database() == "memory"
    assert duckdb_engine.get_default_schema() == "test_schema"

    sql("DROP TABLE test_schema.test_table;", engine=engine)
    sql("DROP SCHEMA test_schema;", engine=engine)


@pytest.mark.skipif(
    not HAS_DUCKDB or not HAS_POLARS or not HAS_PANDAS,
    reason="duckdb, polars and pandas not installed",
)
def test_duckdb_engine_execute_polars_fallback() -> None:
    import pandas as pd

    engine = DuckDBEngine(None, engine_name=VariableName("test_duckdb"))
    # This dtype is currently not supported by polars
    result = engine.execute(
        "select to_days(cast((current_date - DATE '2025-01-01') as INTEGER));"
    )
    assert isinstance(result, pd.DataFrame)


@pytest.mark.skipif(
    not HAS_DUCKDB or not HAS_POLARS or not HAS_PANDAS,
    reason="DuckDB, Polars, and Pandas not installed",
)
def test_duckdb_engine_sql_output_formats(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    """Test DuckDBEngine execute with different SQL output formats."""
    import pandas as pd
    import polars as pl

    # Test with polars output format
    with mock.patch.object(
        DuckDBEngine, "sql_output_format", return_value="polars"
    ):
        engine = DuckDBEngine(
            duckdb_connection, engine_name=VariableName("test_duckdb")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, pl.DataFrame)
        assert len(result) == 4

    # Test with lazy-polars output format
    with mock.patch.object(
        DuckDBEngine, "sql_output_format", return_value="lazy-polars"
    ):
        engine = DuckDBEngine(
            duckdb_connection, engine_name=VariableName("test_duckdb")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, pl.LazyFrame)
        assert len(result.collect()) == 4

    # Test with pandas output format
    with mock.patch.object(
        DuckDBEngine, "sql_output_format", return_value="pandas"
    ):
        engine = DuckDBEngine(
            duckdb_connection, engine_name=VariableName("test_duckdb")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 4

    # Test with native output format
    with mock.patch.object(
        DuckDBEngine, "sql_output_format", return_value="native"
    ):
        engine = DuckDBEngine(
            duckdb_connection, engine_name=VariableName("test_duckdb")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert not isinstance(
            result, (pd.DataFrame, pl.DataFrame, pl.LazyFrame)
        )
        # DuckDB native result has a different interface than SQLAlchemy
        assert hasattr(result, "fetchall") or hasattr(result, "fetch_df")

    # Test with auto output format (should use polars if available)
    with mock.patch.object(
        DuckDBEngine, "sql_output_format", return_value="auto"
    ):
        engine = DuckDBEngine(
            duckdb_connection, engine_name=VariableName("test_duckdb")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, (pd.DataFrame, pl.DataFrame))
        assert len(result) == 4


@pytest.mark.skipif(
    not HAS_DUCKDB or not HAS_POLARS,
    reason="DuckDB and Polars not installed",
)
@pytest.mark.parametrize(
    ("sql_output_format", "expected_type_name"),
    [
        ("polars", "DataFrame"),
        ("lazy-polars", "LazyFrame"),
        ("auto", "DataFrame"),
    ],
)
def test_duckdb_engine_polars_no_pyarrow(
    duckdb_connection: duckdb.DuckDBPyConnection,
    sql_output_format: str,
    expected_type_name: str,
) -> None:
    """Polars conversion should not require pyarrow.

    Uses the Arrow PyCapsule interface (`pl.DataFrame(relation)`) rather than
    `relation.pl()` which historically required pyarrow. Covers every output
    format that routes through `to_polars()` (polars, lazy-polars, and auto
    when polars is installed).
    """
    import polars as pl

    # Block `pyarrow` and any already-imported `pyarrow.*` submodules so that
    # fresh imports raise ModuleNotFoundError.
    blocked_pyarrow = {
        name: None
        for name in list(sys.modules)
        if name == "pyarrow" or name.startswith("pyarrow.")
    }
    blocked_pyarrow["pyarrow"] = None

    with (
        mock.patch.dict(sys.modules, blocked_pyarrow),
        mock.patch.object(
            DuckDBEngine, "sql_output_format", return_value=sql_output_format
        ),
    ):
        engine = DuckDBEngine(
            duckdb_connection,
            engine_name=VariableName("test_duckdb"),
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        expected_type = getattr(pl, expected_type_name)
        assert isinstance(result, expected_type)
        # Collect lazy frames so we exercise the full polars conversion path.
        materialized = (
            result.collect() if expected_type_name == "LazyFrame" else result
        )
        assert len(materialized) == 4


class _RelationProxy:
    # _duckdb.DuckDBPyRelation is a pybind class and rejects attribute
    # assignment, so we wrap it to intercept .pl().
    def __init__(self, relation: Any, pl_override: Any) -> None:
        self._relation = relation
        self._pl_override = pl_override

    def pl(self, *args: Any, **kwargs: Any) -> Any:
        return self._pl_override(self._relation, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._relation, name)


def _run_with_pl_spy(
    duckdb_connection: duckdb.DuckDBPyConnection,
    pl_impl: Any,
) -> tuple[Any, list[dict]]:
    """Execute a lazy-polars query with `pl_impl` wrapping the real `pl()`."""
    from marimo._sql.engines import duckdb as duckdb_engine_mod

    pl_calls: list[dict] = []
    real_wrapped_sql = duckdb_engine_mod.wrapped_sql

    def spy(relation: Any, *args: Any, **kwargs: Any) -> Any:
        pl_calls.append(kwargs)
        return pl_impl(relation, *args, **kwargs)

    def spy_wrapped_sql(query: str, connection: Any) -> Any:
        return _RelationProxy(real_wrapped_sql(query, connection), spy)

    with (
        mock.patch.object(
            DuckDBEngine, "sql_output_format", return_value="lazy-polars"
        ),
        mock.patch.object(
            duckdb_engine_mod, "wrapped_sql", side_effect=spy_wrapped_sql
        ),
    ):
        engine = DuckDBEngine(
            duckdb_connection, engine_name=VariableName("test_duckdb")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")

    return result, pl_calls


@pytest.mark.skipif(
    not HAS_DUCKDB or not HAS_POLARS,
    reason="DuckDB and Polars not installed",
)
def test_duckdb_engine_lazy_polars_uses_streaming(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    # Regression test for #9639: lazy-polars output must stream via
    # pl(lazy=True), not eagerly materialize then .lazy().
    import polars as pl

    def pl_impl(relation: Any, *args: Any, **kwargs: Any) -> Any:
        return relation.pl(*args, **kwargs)

    result, pl_calls = _run_with_pl_spy(duckdb_connection, pl_impl)

    assert isinstance(result, pl.LazyFrame)
    assert len(result.collect()) == 4
    assert pl_calls == [{"batch_size": 100_000, "lazy": True}]


@pytest.mark.skipif(
    not HAS_DUCKDB or not HAS_POLARS,
    reason="DuckDB and Polars not installed",
)
def test_duckdb_engine_lazy_polars_falls_back_on_older_duckdb(
    duckdb_connection: duckdb.DuckDBPyConnection,
) -> None:
    # Regression test for #9639: DuckDB <1.4 rejects the `lazy` kwarg, and
    # `pl(lazy=True)` also fails without pyarrow. Both must fall back to the
    # Arrow PyCapsule path.
    import polars as pl

    def pl_impl(relation: Any, *args: Any, **kwargs: Any) -> Any:
        if "lazy" in kwargs:
            raise TypeError("pl() got an unexpected keyword argument 'lazy'")
        return relation.pl(*args, **kwargs)

    result, pl_calls = _run_with_pl_spy(duckdb_connection, pl_impl)

    assert isinstance(result, pl.LazyFrame)
    assert len(result.collect()) == 4
    # Only the first call (lazy=True, raises) reaches `pl`; the fallback uses
    # `to_polars()` (Arrow PyCapsule) and never touches `relation.pl()`.
    assert pl_calls == [{"batch_size": 100_000, "lazy": True}]
