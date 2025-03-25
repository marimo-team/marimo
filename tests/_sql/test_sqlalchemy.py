"""Tests for SQLAlchemy engines."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from marimo._data.models import Database, DataTable, DataTableColumn, Schema
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.sqlalchemy import (
    SQLAlchemyEngine,
)
from marimo._sql.sql import sql
from marimo._types.ids import VariableName

HAS_SQLALCHEMY = DependencyManager.sqlalchemy.has()
HAS_POLARS = DependencyManager.polars.has()
HAS_PANDAS = DependencyManager.pandas.has()

if TYPE_CHECKING:
    import sqlalchemy as sa

UNUSED_DB_NAME = "unused_db_name"


@pytest.fixture
def empty_sqlite_engine() -> sa.Engine:
    """Create an empty SQLite database for testing."""

    import sqlalchemy as sa

    engine = sa.create_engine("sqlite:///:memory:")
    return engine


@pytest.fixture
def sqlite_engine() -> sa.Engine:
    """Create a temporary SQLite database for testing."""

    import sqlalchemy as sa
    from sqlalchemy import text

    engine = sa.create_engine("sqlite:///:memory:")

    # Test if standard syntax works
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE test (
                    id INTEGER PRIMARY KEY,
                    name TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO test (id, name) VALUES
                (1, 'Alice'),
                (2, 'Bob'),
                (3, 'Charlie')
                """
            )
        )
        # Add another table in another schema
        conn.execute(text("ATTACH ':memory:' AS my_schema"))
        conn.execute(
            text(
                """
                CREATE TABLE my_schema.test2 (
                    id INTEGER PRIMARY KEY,
                    name TEXT
                )
                """
            )
        )

    # Test if mo.sql works
    sql("INSERT INTO test (id, name) VALUES (4, 'Rose')", engine=engine)
    return engine


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_engine_dialect(sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine dialect property."""
    engine = SQLAlchemyEngine(sqlite_engine)
    assert engine.dialect == "sqlite"


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_invalid_engine() -> None:
    """Test SQLAlchemyEngine with an invalid engine and inspector does not raise errors."""

    engine = SQLAlchemyEngine(connection=None)  # type: ignore
    assert engine.inspector is None
    assert engine.default_database is None
    assert engine.default_schema is None


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_empty_engine(empty_sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine with an empty engine."""
    engine = SQLAlchemyEngine(
        connection=empty_sqlite_engine, engine_name=VariableName("sqlite")
    )

    databases = engine.get_databases(
        include_schemas=True, include_tables=True, include_table_details=True
    )
    assert databases == [
        Database(
            name=":memory:",
            dialect="sqlite",
            schemas=[Schema(name="main", tables=[])],
            engine=VariableName("sqlite"),
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


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_sql_types() -> None:
    import sqlalchemy as sa

    sqlite_engine = sa.create_engine("sqlite:///:memory:")

    sql(
        """
        CREATE TABLE all_types (
            col_integer INTEGER,
            col_real REAL,
            col_numeric NUMERIC,
            col_text TEXT,
            col_blob BLOB,
            col_json JSON
        );
    """,
        engine=sqlite_engine,
    )
    sql(
        """
        INSERT INTO all_types (
            col_integer,
            col_real,
            col_numeric,
            col_text,
            col_blob,
            col_json
        ) VALUES
        (
            1,
            1.0,
            1.0,
            'text',
            X'01',
            '{"key": "value"}'
        );
    """,
        engine=sqlite_engine,
    )

    engine = SQLAlchemyEngine(
        sqlite_engine, engine_name=VariableName("test_sqlite")
    )
    tables = engine.get_tables_in_schema(
        schema="main", database=UNUSED_DB_NAME, include_table_details=True
    )

    assert len(tables) == 1
    table = tables[0]
    assert table.source == "sqlite"
    assert table.name == "all_types"
    assert table.num_columns == 6
    assert table.num_rows is None

    columns = table.columns
    assert columns[0].name == "col_integer"
    assert columns[0].type == "integer"
    assert columns[0].external_type == "INTEGER"
    assert columns[0].sample_values == []  # not implemented

    assert columns[1].name == "col_real"
    assert columns[1].type == "number"
    assert columns[1].external_type == "REAL"

    assert columns[2].name == "col_numeric"
    assert columns[2].type == "number"
    assert columns[2].external_type == "NUMERIC"

    assert columns[3].name == "col_text"
    assert columns[3].type == "string"
    assert columns[3].external_type == "TEXT"

    assert columns[4].name == "col_blob"
    assert columns[4].type == "string"
    assert columns[4].external_type == "BLOB"

    assert columns[5].name == "col_json"
    assert columns[5].type == "string"
    assert columns[5].external_type == "JSON"


def get_expected_table(
    table_name: str, include_table_details: bool = True
) -> DataTable:
    "This test can be reused for sqlite_engine"
    return DataTable(
        source_type="connection",
        source="sqlite",
        name=table_name,
        num_rows=None,
        num_columns=2 if include_table_details else None,
        variable_name=None,
        engine=VariableName("test_sqlite"),
        primary_keys=["id"] if include_table_details else [],
        indexes=[],
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
                external_type="TEXT",
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


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_engine_get_table_details(sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine get_table method."""
    engine = SQLAlchemyEngine(
        sqlite_engine, engine_name=VariableName("test_sqlite")
    )
    table = engine.get_table_details(
        table_name="test", schema_name="main", database_name=UNUSED_DB_NAME
    )
    assert table == get_expected_table("test")

    # different schema
    table = engine.get_table_details(
        table_name="test2",
        schema_name="my_schema",
        database_name=UNUSED_DB_NAME,
    )
    assert table == get_expected_table("test2")

    # non-existent table
    assert (
        engine.get_table_details(
            table_name="non_existent",
            schema_name="main",
            database_name=UNUSED_DB_NAME,
        )
        is None
    )

    # non-existent schema
    assert (
        engine.get_table_details(
            table_name="test",
            schema_name="non_existent",
            database_name=UNUSED_DB_NAME,
        )
        is None
    )


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_engine_get_tables_in_schema(
    sqlite_engine: sa.Engine,
) -> None:
    """Test SQLAlchemyEngine get_tables method."""
    engine = SQLAlchemyEngine(
        sqlite_engine, engine_name=VariableName("test_sqlite")
    )
    tables = engine.get_tables_in_schema(
        schema="main", database=UNUSED_DB_NAME, include_table_details=True
    )

    assert isinstance(tables, list)
    assert len(tables) == 1
    assert tables[0] == get_expected_table("test")

    # Test with other schema
    tables = engine.get_tables_in_schema(
        schema="my_schema", database=UNUSED_DB_NAME, include_table_details=True
    )
    assert isinstance(tables, list)
    assert len(tables) == 1
    assert tables[0] == get_expected_table("test2")

    # Test with non-existent schema
    assert (
        engine.get_tables_in_schema(
            schema="non_existent",
            database=UNUSED_DB_NAME,
            include_table_details=True,
        )
        == []
    )

    # Test with include_table_details false
    tables = engine.get_tables_in_schema(
        schema="main", database=UNUSED_DB_NAME, include_table_details=False
    )
    assert isinstance(tables, list)
    assert len(tables) == 1
    expected_table = get_expected_table("test", False)
    assert tables[0] == expected_table


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_engine_get_schemas(sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine get_schemas method."""
    engine = SQLAlchemyEngine(
        sqlite_engine, engine_name=VariableName("test_sqlite")
    )
    schemas = engine._get_schemas(
        database=UNUSED_DB_NAME,
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
        database=UNUSED_DB_NAME,
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
        database=UNUSED_DB_NAME,
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


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_get_databases(sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine get_databases method."""
    engine = SQLAlchemyEngine(
        sqlite_engine, engine_name=VariableName("test_sqlite")
    )
    databases = engine.get_databases(
        include_schemas=True, include_tables=True, include_table_details=True
    )

    assert databases == [
        Database(
            name=":memory:",
            dialect="sqlite",
            schemas=[
                get_expected_schema("main", "test"),
                get_expected_schema("my_schema", "test2"),
            ],
            engine=VariableName("test_sqlite"),
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
            name=":memory:",
            dialect="sqlite",
            schemas=[
                Schema(name="main", tables=[tables_main]),
                Schema(name="my_schema", tables=[tables_my_schema]),
            ],
            engine=VariableName("test_sqlite"),
        )
    ]

    # Test with include_tables false
    databases = engine.get_databases(
        include_schemas=True, include_tables=False, include_table_details=True
    )
    assert databases == [
        Database(
            name=":memory:",
            dialect="sqlite",
            schemas=[
                Schema(name="main", tables=[]),
                Schema(name="my_schema", tables=[]),
            ],
            engine=VariableName("test_sqlite"),
        )
    ]

    # Test with include_schemas false
    databases = engine.get_databases(
        include_schemas=False, include_tables=True, include_table_details=True
    )
    assert databases == [
        Database(
            name=":memory:",
            dialect="sqlite",
            schemas=[],
            engine=VariableName("test_sqlite"),
        )
    ]

    # Test with include_schemas and include_tables false
    databases = engine.get_databases(
        include_schemas=False, include_tables=False, include_table_details=True
    )
    assert databases == [
        Database(
            name=":memory:",
            dialect="sqlite",
            schemas=[],
            engine=VariableName("test_sqlite"),
        )
    ]


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_get_databases_auto(sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine get_databases method with 'auto' option."""
    engine = SQLAlchemyEngine(
        sqlite_engine, engine_name=VariableName("test_sqlite")
    )

    # For SQLite, _is_cheap_discovery() returns True, so 'auto' should behave like True
    databases = engine.get_databases(
        include_schemas="auto",
        include_tables="auto",
        include_table_details="auto",
    )

    # Should be equivalent to setting all params to True since sqlite is a "cheap" dialect
    tables_main = get_expected_table("test", include_table_details=True)
    tables_my_schema = get_expected_table("test2", include_table_details=True)
    assert tables_main.columns == tables_my_schema.columns
    assert tables_main.primary_keys == tables_my_schema.primary_keys
    assert databases == [
        Database(
            name=":memory:",
            dialect="sqlite",
            schemas=[
                get_expected_schema("main", "test"),
                get_expected_schema("my_schema", "test2"),
            ],
            engine=VariableName("test_sqlite"),
        )
    ]

    # Test with a mock to simulate a non-cheap dialect
    with mock.patch.object(
        SQLAlchemyEngine, "_is_cheap_discovery", return_value=False
    ):
        # For a non-cheap dialect, 'auto' should behave like False
        databases = engine.get_databases(
            include_schemas="auto",
            include_tables="auto",
            include_table_details="auto",
        )

        assert databases == [
            Database(
                name=":memory:",
                dialect="sqlite",
                schemas=[],
                engine=VariableName("test_sqlite"),
            )
        ]


@pytest.mark.skipif(
    not HAS_SQLALCHEMY or not HAS_PANDAS,
    reason="SQLAlchemy and Pandas not installed",
)
def test_sqlalchemy_engine_execute(sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine execute."""
    import pandas as pd
    import polars as pl

    engine = SQLAlchemyEngine(sqlite_engine)
    result = engine.execute("SELECT * FROM test ORDER BY id")
    assert isinstance(result, (pd.DataFrame, pl.DataFrame))
    assert len(result) == 4


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_get_database_name(sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine get_database_name."""
    engine = SQLAlchemyEngine(sqlite_engine)
    assert engine.get_default_database() == ":memory:"

    import sqlalchemy as sa

    # Test with no database name
    engine = SQLAlchemyEngine(sa.create_engine("sqlite:///"))
    assert engine.get_default_database() == ""
