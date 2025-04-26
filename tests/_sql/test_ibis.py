"""Tests for Ibis engines."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from marimo._data.models import Database, DataTable, DataTableColumn, Schema
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.ibis import IbisEngine
from marimo._sql.sql import sql
from marimo._types.ids import VariableName

HAS_IBIS = DependencyManager.ibis.has()
HAS_POLARS = DependencyManager.polars.has()
HAS_PANDAS = DependencyManager.pandas.has()

if TYPE_CHECKING:
    from ibis.backends.sql import SQLBackend


UNUSED_DB_NAME = "unused_db_name"


@pytest.fixture
def empty_ibis_backend() -> SQLBackend:
    """Create an empty in-memory DuckDB database for testing with Ibis."""
    import ibis

    backend = ibis.duckdb.connect()
    return backend


@pytest.fixture
def ibis_backend() -> SQLBackend:
    """Create an in-memory DuckDB database for testing with Ibis."""

    import ibis

    backend = ibis.duckdb.connect()

    data_table = ibis.memtable(
        {"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]}
    )

    backend.create_table("test", obj=data_table)

    backend.create_database("my_schema")
    backend.create_table(
        "test2",
        schema=ibis.schema({"id": "int", "name": "str"}),
        database="my_schema",
    )

    # Test if mo.sql works
    sql("SELECT * FROM test", engine=backend)
    return backend


def get_expected_table(
    table_name: str, include_table_details: bool = True
) -> DataTable:
    "This test can be reused for ibis_backend"
    return DataTable(
        source_type="connection",
        source="ibis",
        name=table_name,
        num_rows=None,
        num_columns=2 if include_table_details else None,
        variable_name=None,
        engine=VariableName("my_ibis"),
        primary_keys=None,
        indexes=None,
        columns=[
            DataTableColumn(
                name="id",
                type="integer",
                external_type="int64",
                sample_values=[],
            ),
            DataTableColumn(
                name="name",
                type="string",
                external_type="string",
                sample_values=[],
            ),
        ]
        if include_table_details
        else [],
    )


def get_expected_schema(schema_name: str, table_name: str) -> Schema:
    return Schema(
        name=schema_name,
        tables=[get_expected_table(table_name)],
    )


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_ibis_engine_dialect(ibis_backend: SQLBackend) -> None:
    """Test IbisEngine dialect property."""
    engine = IbisEngine(ibis_backend, engine_name=VariableName("test_ibis"))
    assert engine.dialect == "duckdb"


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_ibis_get_database_name(ibis_backend: SQLBackend) -> None:
    """Test IbisEngine get_database_name."""
    engine = IbisEngine(ibis_backend, engine_name=VariableName("my_ibis"))
    assert engine.get_default_database() == "memory"


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_ibis_invalid_engine() -> None:
    """Test IbisEngine with an invalid backend and inspector does not raise errors."""

    engine = IbisEngine(connection=None, engine_name=None)  # type: ignore
    assert engine._backend is None
    assert engine.default_database is None
    assert engine.default_schema is None


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_ibis_empty_engine(empty_ibis_backend: SQLBackend) -> None:
    """Test IbisEngine with an empty engine."""
    engine_name = VariableName("my_ibis")
    engine = IbisEngine(connection=empty_ibis_backend, engine_name=engine_name)

    databases = engine.get_databases(
        include_schemas=True, include_tables=True, include_table_details=True
    )
    assert databases == [
        Database(
            name="memory",
            dialect="duckdb",
            schemas=[Schema(name="main", tables=[])],
            engine=engine_name,
        )
    ]

    tables = engine.get_tables_in_schema(
        schema="main", database=UNUSED_DB_NAME, include_table_details=False
    )
    assert tables == []

    table_info = engine.get_table_details(
        table_name="test", schema_name="main", database_name=UNUSED_DB_NAME
    )
    assert table_info is None


# # TODO
# @pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
# def test_ibis_sql_types() -> None:
#     import ibis

#     ibis_backend = ibis.duckdb.connect()

#     data_table = ibis.memtable(
#         {
#             "col_integer": [],
#             "col_real": [],
#             "col_numeric": [],
#             "col_text": [],
#             "col_blob": [],
#             "col_json": [],
#         }
#     )


#     sql(
#         """
#         CREATE TABLE all_types (
#             col_integer INTEGER,
#             col_real REAL,
#             col_numeric NUMERIC,
#             col_text TEXT,
#             col_blob BLOB,
#             col_json JSON
#         );
#     """,
#         engine=sqlite_engine,
#     )
#     sql(
#         """
#         INSERT INTO all_types (
#             col_integer,
#             col_real,
#             col_numeric,
#             col_text,
#             col_blob,
#             col_json
#         ) VALUES
#         (
#             1,
#             1.0,
#             1.0,
#             'text',
#             X'01',
#             '{"key": "value"}'
#         );
#     """,
#         engine=sqlite_engine,
#     )

#     engine = SQLAlchemyEngine(
#         sqlite_engine, engine_name=VariableName("test_sqlite")
#     )
#     tables = engine.get_tables_in_schema(
#         schema="main", database=UNUSED_DB_NAME, include_table_details=True
#     )

#     assert len(tables) == 1
#     table = tables[0]
#     assert table.source == "sqlite"
#     assert table.name == "all_types"
#     assert table.num_columns == 6
#     assert table.num_rows is None

#     columns = table.columns
#     assert columns[0].name == "col_integer"
#     assert columns[0].type == "integer"
#     assert columns[0].external_type == "INTEGER"
#     assert columns[0].sample_values == []  # not implemented

#     assert columns[1].name == "col_real"
#     assert columns[1].type == "number"
#     assert columns[1].external_type == "REAL"

#     assert columns[2].name == "col_numeric"
#     assert columns[2].type == "number"
#     assert columns[2].external_type == "NUMERIC"

#     assert columns[3].name == "col_text"
#     assert columns[3].type == "string"
#     assert columns[3].external_type == "TEXT"

#     assert columns[4].name == "col_blob"
#     assert columns[4].type == "string"
#     assert columns[4].external_type == "BLOB"

#     assert columns[5].name == "col_json"
#     assert columns[5].type == "string"
#     assert columns[5].external_type == "JSON"


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_igis_engine_get_table_details(ibis_backend: SQLBackend) -> None:
    """Test IbisEngine get_table method."""
    engine = IbisEngine(ibis_backend, engine_name=VariableName("my_ibis"))
    table = engine.get_table_details(
        table_name="test", schema_name="main", database_name="memory"
    )
    assert table == get_expected_table("test")

    # different schema
    table = engine.get_table_details(
        table_name="test2",
        schema_name="my_schema",
        database_name="memory",
    )
    assert table == get_expected_table("test2")

    # non-existent table
    assert (
        engine.get_table_details(
            table_name="non_existent",
            schema_name="main",
            database_name="memory",
        )
        is None
    )

    # non-existent schema
    assert (
        engine.get_table_details(
            table_name="test",
            schema_name="non_existent",
            database_name="memory",
        )
        is None
    )


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_ibis_engine_get_tables_in_schema(ibis_backend: SQLBackend) -> None:
    """Test IbisEngine get_tables method."""
    engine = IbisEngine(ibis_backend, engine_name=VariableName("my_ibis"))
    tables = engine.get_tables_in_schema(
        schema="main", database="memory", include_table_details=True
    )

    assert isinstance(tables, list)
    assert len(tables) == 1
    assert tables[0] == get_expected_table("test")

    # Test with other schema
    tables = engine.get_tables_in_schema(
        schema="my_schema", database="memory", include_table_details=True
    )
    assert isinstance(tables, list)
    assert len(tables) == 1
    assert tables[0] == get_expected_table("test2")

    # Test with non-existent schema
    assert (
        engine.get_tables_in_schema(
            schema="non_existent",
            database="memory",
            include_table_details=True,
        )
        == []
    )

    # Test with include_table_details false
    tables = engine.get_tables_in_schema(
        schema="main", database="memory", include_table_details=False
    )
    assert isinstance(tables, list)
    assert len(tables) == 1
    expected_table = get_expected_table("test", False)
    assert tables[0] == expected_table


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_ibis_engine_get_schemas(ibis_backend: SQLBackend) -> None:
    """Test IbisEngine get_schemas method."""
    var_name = VariableName("my_ibis")
    engine = IbisEngine(ibis_backend, engine_name=var_name)
    schemas = engine._get_schemas(
        database="memory",
        include_tables=True,
        include_table_details=True,
    )

    assert isinstance(schemas, list)
    assert len(schemas) == 2

    schema = schemas[0]
    assert schema == get_expected_schema("main", "test")

    schema = schemas[1]
    assert schema == get_expected_schema("my_schema", "test2")

    # Test with include_table_details false
    schemas = engine._get_schemas(
        database="memory",
        include_tables=True,
        include_table_details=False,
    )
    assert isinstance(schemas, list)
    assert len(schemas) == 2

    schema = schemas[0]
    assert schema.name == "main"
    assert len(schema.tables) == 1

    expected_table = get_expected_table("test", include_table_details=False)
    assert schema.tables[0] == expected_table

    # Test with include_tables false
    schemas = engine._get_schemas(
        database="memory",
        include_tables=False,
        include_table_details=True,
    )
    assert isinstance(schemas, list)
    assert len(schemas) == 2

    schema = schemas[0]
    assert schema.name == "main"
    assert len(schema.tables) == 0

    schema = schemas[1]
    assert schema.name == "my_schema"
    assert len(schema.tables) == 0


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_ibis_get_databases(ibis_backend: SQLBackend) -> None:
    """Test IbisEngine get_databases method."""
    var_name = VariableName("my_ibis")
    engine = IbisEngine(ibis_backend, engine_name=var_name)
    databases = engine.get_databases(
        include_schemas=True, include_tables=True, include_table_details=True
    )

    assert databases == [
        Database(
            name="memory",
            dialect="duckdb",
            schemas=[
                get_expected_schema("main", "test"),
                get_expected_schema("my_schema", "test2"),
            ],
            engine=var_name,
        )
    ]

    # Test with include_table_details false
    databases = engine.get_databases(
        include_schemas=True, include_tables=True, include_table_details=False
    )
    tables_main = get_expected_table("test", include_table_details=False)
    tables_my_schema = get_expected_table("test2", include_table_details=False)

    assert databases == [
        Database(
            name="memory",
            dialect="duckdb",
            schemas=[
                Schema(name="main", tables=[tables_main]),
                Schema(name="my_schema", tables=[tables_my_schema]),
            ],
            engine=var_name,
        )
    ]

    # Test with include_tables false
    databases = engine.get_databases(
        include_schemas=True, include_tables=False, include_table_details=True
    )
    assert databases == [
        Database(
            name="memory",
            dialect="duckdb",
            schemas=[
                Schema(name="main", tables=[]),
                Schema(name="my_schema", tables=[]),
            ],
            engine=var_name,
        )
    ]

    # Test with include_schemas false
    databases = engine.get_databases(
        include_schemas=False, include_tables=True, include_table_details=True
    )
    assert databases == [
        Database(
            name="memory",
            dialect="duckdb",
            schemas=[],
            engine=var_name,
        )
    ]

    # Test with include_schemas and include_tables false
    databases = engine.get_databases(
        include_schemas=False, include_tables=False, include_table_details=True
    )
    assert databases == [
        Database(
            name="memory",
            dialect="duckdb",
            schemas=[],
            engine=var_name,
        )
    ]


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_ibis_get_databases_auto(ibis_backend: SQLBackend) -> None:
    """Test IbisEngine get_databases method with 'auto' option."""
    var_name = VariableName("my_ibis")
    engine = IbisEngine(ibis_backend, engine_name=var_name)

    # 'auto' should behave like True
    databases = engine.get_databases(
        include_schemas="auto",
        include_tables="auto",
        include_table_details="auto",
    )

    # Should be equivalent to setting all params to True
    tables_main = get_expected_table("test", include_table_details=True)
    tables_my_schema = get_expected_table("test2", include_table_details=True)
    assert tables_main.columns == tables_my_schema.columns
    assert tables_main.primary_keys == tables_my_schema.primary_keys
    assert databases == [
        Database(
            name="memory",
            dialect="duckdb",
            schemas=[
                get_expected_schema("main", "test"),
                get_expected_schema("my_schema", "test2"),
            ],
            engine=var_name,
        )
    ]

    # Test with a mock to simulate a non-cheap dialect
    with mock.patch.object(
        IbisEngine, "_is_cheap_discovery", return_value=False
    ):
        # For a non-cheap dialect, 'auto' should behave like False
        databases = engine.get_databases(
            include_schemas="auto",
            include_tables="auto",
            include_table_details="auto",
        )

        assert databases == [
            Database(
                name="memory",
                dialect="duckdb",
                schemas=[],
                engine=var_name,
            )
        ]


@pytest.mark.skipif(
    not HAS_IBIS or not HAS_PANDAS,
    reason="Ibis and Pandas not installed",
)
def test_ibis_engine_execute(ibis_backend: SQLBackend) -> None:
    """Test Ibis execute."""
    import pandas as pd
    import polars as pl

    engine = IbisEngine(ibis_backend, engine_name=VariableName("my_ibis"))
    result = engine.execute("SELECT * FROM test ORDER BY id")
    assert isinstance(result, (pd.DataFrame, pl.DataFrame))
    assert len(result) == 3


@pytest.mark.skipif(
    not HAS_IBIS or not HAS_POLARS or not HAS_PANDAS,
    reason="Ibis, Polars, and Pandas not installed",
)
def test_ibis_engine_sql_output_formats(ibis_backend: SQLBackend) -> None:
    """Test IbisEngine execute with different SQL output formats."""
    import pandas as pd
    import polars as pl
    from ibis import Expr

    # Test with polars output format
    with mock.patch.object(
        IbisEngine, "sql_output_format", return_value="polars"
    ):
        engine = IbisEngine(ibis_backend, engine_name=VariableName("my_ibis"))
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, pl.DataFrame)
        assert len(result) == 3

    # Test with lazy-polars output format
    with mock.patch.object(
        IbisEngine, "sql_output_format", return_value="lazy-polars"
    ):
        engine = IbisEngine(ibis_backend, engine_name=VariableName("my_ibis"))
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, pl.LazyFrame)
        assert len(result.collect()) == 3

    # Test with pandas output format
    with mock.patch.object(
        IbisEngine, "sql_output_format", return_value="pandas"
    ):
        engine = IbisEngine(ibis_backend, engine_name=VariableName("my_ibis"))
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3

    # Test with native output format
    with mock.patch.object(
        IbisEngine, "sql_output_format", return_value="native"
    ):
        engine = IbisEngine(ibis_backend, engine_name=VariableName("my_ibis"))
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert not isinstance(
            result, (pd.DataFrame, pl.DataFrame, pl.LazyFrame)
        )
        assert isinstance(result, Expr)

    # Test with auto output format (should use polars if available)
    with mock.patch.object(
        IbisEngine, "sql_output_format", return_value="auto"
    ):
        engine = IbisEngine(ibis_backend, engine_name=VariableName("my_ibis"))
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, (pd.DataFrame, pl.DataFrame))
        assert len(result) == 3
