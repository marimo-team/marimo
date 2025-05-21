"""Tests for Ibis engines."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from marimo._data.models import Database, DataTable, DataTableColumn, Schema
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.ibis import IbisEngine, IbisToMarimoConversionError
from marimo._sql.engines.types import EngineCatalog, QueryEngine
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
def test_engine_compatibility() -> None:
    """Test engine compatibility checks."""
    from ibis.backends.sql import SQLBackend

    obj = object()
    mock_ibis = mock.MagicMock(spec=SQLBackend)

    assert IbisEngine.is_compatible(mock_ibis)
    assert not IbisEngine.is_compatible(obj)


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_engine_name_initialization() -> None:
    import ibis

    ibis_backend = ibis.duckdb.connect()  # in-memory connection
    ibis_engine = IbisEngine(ibis_backend, engine_name="my_ibis")
    assert ibis_engine._engine_name == "my_ibis"

    # Test default name
    ibis_engine = IbisEngine(ibis_backend)
    assert ibis_engine._engine_name is None

    assert isinstance(ibis_engine, IbisEngine)
    assert isinstance(ibis_engine, EngineCatalog)
    assert isinstance(ibis_engine, QueryEngine)


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_ibis_engine_source_and_dialect() -> None:
    """Test IbisEngine source and dialect properties."""
    import ibis

    sqlite_con = ibis.sqlite.connect()  # in-memory
    sqlite_engine = IbisEngine(sqlite_con)
    assert sqlite_engine.source == "ibis"
    assert sqlite_engine.dialect == "sqlite"

    duckdb_con = ibis.duckdb.connect()  # in-memory
    duckdb_engine = IbisEngine(duckdb_con)
    assert duckdb_engine.source == "ibis"
    assert duckdb_engine.dialect == "duckdb"


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_ibis_engine_get_database_name(ibis_backend: SQLBackend) -> None:
    """Test IbisEngine get_database_name."""
    engine = IbisEngine(ibis_backend, engine_name=VariableName("my_ibis"))
    assert engine.get_default_database() == "memory"


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_ibis_invalid_engine() -> None:
    """Test IbisEngine with an invalid backend and inspector does not raise errors."""

    engine = IbisEngine(connection=None, engine_name=None)  # type: ignore
    assert engine._connection is None
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


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_ibis_sql_types() -> None:
    import ibis
    import ibis.expr.datatypes as dt

    ALL_TYPES = (
        dt.Boolean(),
        dt.Int8(),
        dt.Int16(),
        dt.Int32(),
        dt.Int64(),
        dt.UInt8(),
        dt.UInt16(),
        dt.UInt32(),
        dt.UInt64(),
        dt.Float16(),
        dt.Float32(),
        dt.Float64(),
        dt.Decimal(),
        dt.Binary(),
        dt.String(),
        dt.Date(),
        dt.Time(),
        dt.Timestamp(),
        dt.Interval(unit="D"),
        dt.Array(value_type=dt.Int32()),
        dt.Map(key_type=dt.String(), value_type=dt.Int32()),
        dt.Struct(fields={"foo": dt.Int32()}),
        dt.JSON(),
        dt.MACADDR(),
        dt.UUID(),
        # dt.Null(),  # not supported in duckdb
        # dt.MultiLineString(),  # is a duckdb extension
        # dt.MultiPoint(),  # is a duckdb extension
        # dt.MultiPolygon(),  # is a duckdb extension
        # dt.Point(),  # is a duckdb extension
        # dt.Polygon(),  # is a duckdb extension
    )
    expected_external_type = {
        str(dt.Boolean()): "boolean",
        str(dt.Int8()): "int8",
        str(dt.Int16()): "int16",
        str(dt.Int32()): "int32",
        str(dt.Int64()): "int64",
        str(dt.UInt8()): "uint8",
        str(dt.UInt16()): "uint16",
        str(dt.UInt32()): "uint32",
        str(dt.UInt64()): "uint64",
        str(dt.Float16()): "float32",  # duckdb does not support float16
        str(dt.Float32()): "float32",
        str(dt.Float64()): "float64",
        str(
            dt.Decimal()
        ): "decimal(18, 3)",  # duckdb sets default precision and scale
        str(dt.Binary()): "binary",
        str(dt.String()): "string",
        str(dt.Date()): "date",
        str(dt.Time()): "time",
        str(dt.Timestamp()): "timestamp",  # duckdb sets default precision
        str(dt.Interval(unit="D")): "interval('us')",
        str(dt.Array(value_type=dt.Int32())): "array<int32>",
        str(
            dt.Map(key_type=dt.String(), value_type=dt.Int32())
        ): "map<string, int32>",
        str(dt.Struct(fields={"foo": dt.Int32()})): "struct<foo: int32>",
        str(dt.JSON()): "json",
        str(dt.MACADDR()): "string",
        str(dt.UUID()): "uuid",
    }
    expected_marimo_type = {
        str(dt.Boolean()): "boolean",
        str(dt.Int8()): "integer",
        str(dt.Int16()): "integer",
        str(dt.Int32()): "integer",
        str(dt.Int64()): "integer",
        str(dt.UInt8()): "integer",
        str(dt.UInt16()): "integer",
        str(dt.UInt32()): "integer",
        str(dt.UInt64()): "integer",
        str(dt.Float16()): "number",
        str(dt.Float32()): "number",
        str(dt.Float64()): "number",
        str(dt.Decimal()): "number",
        str(dt.Binary()): "string",
        str(dt.String()): "string",
        str(dt.Date()): "date",
        str(dt.Time()): "time",
        str(dt.Timestamp()): "datetime",
        str(dt.Interval(unit="D")): "string",  # default case
        str(dt.Array(value_type=dt.Int32())): "unknown",
        str(dt.Map(key_type=dt.String(), value_type=dt.Int32())): "unknown",
        str(dt.Struct(fields={"foo": dt.Int32()})): "unknown",
        str(dt.JSON()): "unknown",  # default case
        str(dt.MACADDR()): "string",  # default case
        str(dt.UUID()): "string",  # default case
    }

    ibis_backend = ibis.duckdb.connect()
    schema = ibis.schema({str(t): t for t in ALL_TYPES})
    ibis_backend.create_table("all_types", schema=schema)

    engine = IbisEngine(ibis_backend, engine_name=VariableName("my_ibis"))
    tables = engine.get_tables_in_schema(
        schema="main", database="memory", include_table_details=True
    )

    assert len(tables) == 1
    table = tables[0]
    assert table.source == "ibis"
    assert table.name == "all_types"
    assert table.num_columns == 25
    assert table.num_rows is None

    for column in table.columns:
        assert column.name in expected_marimo_type.keys()
        assert column.type == expected_marimo_type[column.name], (
            f"{column.name} {column.type} {expected_marimo_type[column.name]}"
        )
        assert column.external_type == expected_external_type[column.name], (
            f"{column.name} {column.external_type} {expected_external_type[column.name]}"
        )


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_ibis_type_conversion() -> None:
    """Test IbisEngine _ibis_to_marimo_dtype.

    The IbisToMarimoConversionError should be caught by calling function (e.g., .get_table_details())
    Attempts to exhaustively test type conversion

    reference: https://ibis-project.org/reference/datatypes
    """
    import ibis.expr.datatypes as dt

    to_marimo = IbisEngine._ibis_to_marimo_dtype

    assert to_marimo(dt.Boolean()) == "boolean"

    assert to_marimo(dt.Int8()) == "integer"
    assert to_marimo(dt.Int16()) == "integer"
    assert to_marimo(dt.Int32()) == "integer"
    assert to_marimo(dt.Int64()) == "integer"
    assert to_marimo(dt.UInt8()) == "integer"
    assert to_marimo(dt.UInt16()) == "integer"
    assert to_marimo(dt.UInt32()) == "integer"
    assert to_marimo(dt.UInt64()) == "integer"

    assert to_marimo(dt.Decimal()) == "number"
    assert to_marimo(dt.Float16()) == "number"
    assert to_marimo(dt.Float32()) == "number"
    assert to_marimo(dt.Float64()) == "number"

    # Binary is a sequence of bytes
    assert to_marimo(dt.Binary()) == "string"
    assert to_marimo(dt.String()) == "string"

    # temporal
    assert to_marimo(dt.Date()) == "date"
    assert to_marimo(dt.Time()) == "time"
    assert to_marimo(dt.Timestamp()) == "datetime"

    # geometry
    with pytest.raises(IbisToMarimoConversionError):
        to_marimo(dt.MultiPoint())

    with pytest.raises(IbisToMarimoConversionError):
        to_marimo(dt.MultiPolygon())

    with pytest.raises(IbisToMarimoConversionError):
        to_marimo(dt.Null())

    with pytest.raises(IbisToMarimoConversionError):
        to_marimo(dt.Point())

    with pytest.raises(IbisToMarimoConversionError):
        to_marimo(dt.Polygon())


@pytest.mark.skipif(not HAS_IBIS, reason="Ibis not installed")
def test_ibis_engine_get_table_details(ibis_backend: SQLBackend) -> None:
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
def test_ibis_engine_get_databases(ibis_backend: SQLBackend) -> None:
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
def test_ibis_engine_get_databases_auto(ibis_backend: SQLBackend) -> None:
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
    not HAS_IBIS or not (HAS_PANDAS or HAS_POLARS),
    reason="Ibis and either pandas or polars not installed",
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
