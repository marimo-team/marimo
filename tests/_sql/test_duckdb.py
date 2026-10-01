# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

import sys
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Literal
from unittest import mock

import pytest

from marimo._data.models import Database, DataTable, DataTableColumn, Schema
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.duckdb import DuckDBEngine
from marimo._sql.engines.types import EngineCatalog, QueryEngine
from marimo._sql.get_engines import engine_to_data_source_connection
from marimo._sql.sql import sql
from marimo._sql.sql_quoting import quote_qualified_name
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
        schemas=[
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

    assert databases == [
        *expected_databases_with_conn,
        Database(
            name="temp",
            dialect="duckdb",
            engine=VariableName("test_duckdb"),
            schemas=[Schema(name="main", tables=[])],
        ),
    ]


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
        Database(
            name=name, dialect="duckdb", schemas=[], schemas_resolved=False
        )
        for name in ("memory", "temp")
    ]
    assert engine.get_default_database() == "memory"
    assert engine.get_default_schema() == "main"

    engine.execute(
        "CREATE TABLE test (id INTEGER PRIMARY KEY, name VARCHAR(255))"
    )
    try:
        engine.execute(
            """
            INSERT INTO test VALUES
            (1, 'Alice'),
            (2, 'Bob'),
            (3, 'Charlie');
            """
        )
        databases = engine.get_databases(
            include_schemas=True,
            include_tables=True,
            include_table_details=True,
        )

        expected_databases = deepcopy(expected_databases_with_conn)
        expected_databases[0].engine = None
        expected_databases[0].schemas[0].tables[0].engine = None
        expected_databases[0].schemas[0].tables[0].source_type = "duckdb"
        expected_databases[0].schemas[0].tables[0].source = "memory"

        assert databases == [
            *expected_databases,
            Database(
                name="temp",
                dialect="duckdb",
                schemas=[Schema(name="main", tables=[])],
            ),
        ]
    finally:
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


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
@pytest.mark.parametrize("include_schemas", [False, True, "auto"])
@pytest.mark.parametrize("include_tables", [False, True, "auto"])
@pytest.mark.parametrize("include_details", [False, True, "auto"])
def test_duckdb_discovery_depth(
    include_schemas: bool | Literal["auto"],
    include_tables: bool | Literal["auto"],
    include_details: bool | Literal["auto"],
) -> None:
    import duckdb

    with duckdb.connect() as connection:
        connection.execute("CREATE TABLE test (id INTEGER, name VARCHAR)")
        engine = DuckDBEngine(connection, VariableName("test_duckdb"))
        with (
            mock.patch.object(
                engine, "_query_catalog", wraps=engine._query_catalog
            ) as query,
            mock.patch.object(
                engine, "get_table_details", wraps=engine.get_table_details
            ) as details,
        ):
            databases = engine.get_databases(
                include_schemas=include_schemas,
                include_tables=include_tables,
                include_table_details=include_details,
            )

        schemas_enabled = include_schemas is not False
        tables_enabled = schemas_enabled and include_tables is not False
        details_enabled = tables_enabled and include_details is not False
        expected = deepcopy(expected_databases_with_conn[0])
        if not schemas_enabled:
            expected.schemas = []
            expected.schemas_resolved = False
        elif not tables_enabled:
            expected.schemas[0].tables = []
            expected.schemas[0].tables_resolved = False
        elif not details_enabled:
            expected.schemas[0].tables[0].columns = []
            expected.schemas[0].tables[0].num_columns = None
        assert databases[0] == expected
        queries = [call.args[0] for call in query.call_args_list]
        assert sum("duckdb_schemas()" in sql for sql in queries) == int(
            schemas_enabled
        )
        assert (
            any("information_schema.tables" in sql for sql in queries)
            == tables_enabled
        )
        assert sum("duckdb_columns()" in sql for sql in queries) == int(
            details_enabled
        )
        assert details.call_count == 0
        assert not any("SHOW ALL TABLES" in sql for sql in queries)


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_deferred_discovery() -> None:
    import duckdb

    database, schema, table_name = 'db".quoted', "schema's.name", 'table".name'
    qualified_table = quote_qualified_name(database, schema, table_name)
    with duckdb.connect() as connection:
        connection.execute(
            f"ATTACH ':memory:' AS {quote_qualified_name(database)}"
        )
        connection.execute(
            f"CREATE SCHEMA {quote_qualified_name(database, schema)}"
        )
        connection.execute(
            f"CREATE TABLE {qualified_table} (id INTEGER, name VARCHAR)"
        )
        connection.execute(
            f"CREATE VIEW {quote_qualified_name(database, schema, 'a_view')} AS SELECT * FROM {qualified_table}"
        )
        connection.execute("CREATE TEMP TABLE local_temp (id INTEGER)")
        engine = DuckDBEngine(connection, VariableName("test_duckdb"))
        databases = engine.get_databases(
            include_schemas=False,
            include_tables=False,
            include_table_details=False,
        )
        assert {db.name for db in databases} == {database, "memory", "temp"}
        assert all(
            not db.schemas_resolved and not db.schemas for db in databases
        )

        schemas = engine.get_schemas(
            database=database,
            include_tables=False,
            include_table_details=False,
        )
        assert schemas == [
            Schema(name="main", tables=[], tables_resolved=False),
            Schema(name=schema, tables=[], tables_resolved=False),
        ]
        tables = engine.get_tables_in_schema(
            database=database, schema=schema, include_table_details=False
        )
        assert [(table.name, table.type) for table in tables] == [
            ("a_view", "view"),
            (table_name, "table"),
        ]
        assert all(
            table.columns == [] and table.num_columns is None
            for table in tables
        )
        expected = deepcopy(
            expected_databases_with_conn[0].schemas[0].tables[0]
        )
        expected.source = database
        for name in (table_name, "a_view"):
            expected.name = name
            expected.type = "view" if name == "a_view" else "table"
            assert (
                engine.get_table_details(
                    database_name=database, schema_name=schema, table_name=name
                )
                == expected
            )
        assert (
            engine.get_table_details(
                database_name=database,
                schema_name=schema,
                table_name="missing",
            )
            is None
        )
        assert (
            engine.get_schemas(
                database=database,
                include_tables=False,
                include_table_details=False,
                schema_path=[schema],
            )
            == []
        )
        assert [
            table.name
            for table in engine.get_tables_in_schema(
                database="temp", schema="main", include_table_details=False
            )
        ] == ["local_temp"]
        assert engine.get_schemas(
            database=None, include_tables=False, include_table_details=False
        ) == [Schema(name="main", tables=[], tables_resolved=False)]


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
@pytest.mark.parametrize("disable_discovery", [False, True])
def test_duckdb_discovery_config(disable_discovery: bool) -> None:
    import duckdb

    with duckdb.connect() as connection:
        connection.execute("CREATE TABLE test (id INTEGER)")
        name = VariableName("connection")
        engine = DuckDBEngine(connection, name)
        config = {}
        if disable_discovery:
            config = {
                "auto_discover_schemas": False,
                "auto_discover_tables": False,
                "auto_discover_columns": False,
            }
        with mock.patch(
            "marimo._sql.get_engines.get_datasources_config",
            return_value=config,
        ):
            source = engine_to_data_source_connection(name, engine)
        if disable_discovery:
            assert source.databases == [
                Database(
                    name=db,
                    dialect="duckdb",
                    engine=name,
                    schemas=[],
                    schemas_resolved=False,
                )
                for db in ("memory", "temp")
            ]
        else:
            # The default discovers table names but defers columns.
            assert source.databases[0].schemas[0].tables == [
                DataTable(
                    name="test",
                    source="memory",
                    source_type="connection",
                    engine=name,
                    num_rows=None,
                    num_columns=None,
                    columns=[],
                    variable_name=None,
                )
            ]


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_discovery_closed_connection() -> None:
    import duckdb

    connection = duckdb.connect()
    connection.close()
    engine = DuckDBEngine(connection)
    assert (
        engine.get_databases(
            include_schemas=True,
            include_tables=True,
            include_table_details=True,
        )
        == []
    )


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
def test_duckdb_discovers_schemas_once_for_all_databases() -> None:
    import duckdb

    with duckdb.connect() as connection:
        for name in ("first", "second"):
            connection.execute(f"ATTACH ':memory:' AS {name}")
            connection.execute(f"CREATE SCHEMA {name}.extra")
        engine = DuckDBEngine(connection)
        with mock.patch.object(
            engine, "_query_catalog", wraps=engine._query_catalog
        ) as query:
            databases = engine.get_databases(
                include_schemas=True,
                include_tables=False,
                include_table_details=False,
            )
        assert databases == [
            Database(
                name=name,
                dialect="duckdb",
                schemas=[
                    Schema(name=schema, tables=[], tables_resolved=False)
                    for schema in schemas
                ],
            )
            for name, schemas in [
                ("first", ["extra", "main"]),
                ("memory", ["main"]),
                ("second", ["extra", "main"]),
                ("temp", ["main"]),
            ]
        ]
        assert len(query.call_args_list) == 2
        assert (
            sum(
                "duckdb_schemas()" in call.args[0]
                for call in query.call_args_list
            )
            == 1
        )


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
@pytest.mark.parametrize("all_databases", [False, True])
def test_duckdb_batches_column_discovery(all_databases: bool) -> None:
    import duckdb

    with duckdb.connect() as connection:
        connection.execute("ATTACH ':memory:' AS attached")
        for database in ("memory", "attached"):
            connection.execute(f"CREATE SCHEMA {database}.extra")
            for schema in ("main", "extra"):
                connection.execute(
                    f"CREATE TABLE {database}.{schema}.example (z INTEGER, a VARCHAR)"
                )
                connection.execute(
                    f"CREATE VIEW {database}.{schema}.example_view AS SELECT * FROM {database}.{schema}.example"
                )
        engine = DuckDBEngine(connection)
        with (
            mock.patch.object(
                engine, "_query_catalog", wraps=engine._query_catalog
            ) as query,
            mock.patch.object(
                engine, "_describe_table", wraps=engine._describe_table
            ) as describe,
        ):
            if all_databases:
                databases = engine.get_databases(
                    include_schemas=True,
                    include_tables=True,
                    include_table_details=True,
                )
                tables = [
                    table
                    for database in databases
                    for schema in database.schemas
                    for table in schema.tables
                ]
            else:
                tables = engine.get_tables_in_schema(
                    database="attached",
                    schema="main",
                    include_table_details=True,
                )
        assert len(tables) == (8 if all_databases else 2)
        for table in tables:
            assert table.columns == [
                DataTableColumn(
                    name="z",
                    type="integer",
                    external_type="INTEGER",
                    sample_values=[],
                ),
                DataTableColumn(
                    name="a",
                    type="string",
                    external_type="VARCHAR",
                    sample_values=[],
                ),
            ]
            assert table.num_columns == 2
            assert table.type == (
                "view" if table.name == "example_view" else "table"
            )
        assert (
            sum(
                "duckdb_columns()" in call.args[0]
                for call in query.call_args_list
            )
            == 1
        )
        describe.assert_not_called()


@pytest.mark.skipif(not HAS_DUCKDB, reason="DuckDB not installed")
@pytest.mark.parametrize("failure", ["query", "missing", "placeholder"])
def test_duckdb_keeps_tables_when_column_discovery_fails(failure: str) -> None:
    import duckdb

    with duckdb.connect() as connection:
        connection.execute("CREATE TABLE example (id INTEGER)")
        engine = DuckDBEngine(connection)
        query = engine._query_catalog

        def failing_columns(
            sql: str, params: list[Any] | None = None
        ) -> list[Any]:
            if "duckdb_columns()" in sql:
                if failure == "query":
                    raise duckdb.NotImplementedException(
                        "Column metadata unavailable"
                    )
                if failure == "placeholder":
                    return [("memory", "main", "example", "__", "INTEGER")]
                return []
            return query(sql, params)

        with (
            mock.patch.object(
                engine, "_query_catalog", side_effect=failing_columns
            ),
            mock.patch(
                "marimo._sql.engines.duckdb.get_table_columns", return_value=[]
            ) as describe,
        ):
            tables = engine.get_tables_in_schema(
                database="memory", schema="main", include_table_details=True
            )
        assert tables == [
            DataTable(
                name="example",
                source="memory",
                source_type="duckdb",
                num_rows=None,
                num_columns=None,
                variable_name=None,
                columns=[],
            )
        ]
        assert describe.call_count == int(failure == "placeholder")
