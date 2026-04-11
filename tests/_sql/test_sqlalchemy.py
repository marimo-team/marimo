# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from marimo._data.models import Database, DataTable, DataTableColumn, Schema
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.sqlalchemy import SQLAlchemyEngine, safe_execute
from marimo._sql.engines.types import EngineCatalog, QueryEngine
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


@pytest.fixture
def sqlite_engine_meta() -> sa.Engine:
    """Create a temporary SQLite database with information_schema.
    Use a mock information_schema"""

    import sqlalchemy as sa

    engine = sa.create_engine("sqlite:///:memory:")

    sql("ATTACH ':memory:' AS information_schema", engine=engine)
    sql(
        "CREATE TABLE information_schema.tables (table_name TEXT)",
        engine=engine,
    )
    sql(
        "INSERT INTO information_schema.tables VALUES ('tables')",
        engine=engine,
    )

    return engine


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_engine_dialect(sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine dialect property."""
    engine = SQLAlchemyEngine(
        sqlite_engine, engine_name=VariableName("test_sqlite")
    )
    assert engine.dialect == "sqlite"


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_engine_is_instance(sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine is an instance of the correct types."""
    engine = SQLAlchemyEngine(
        sqlite_engine, engine_name=VariableName("sqlite")
    )
    assert isinstance(engine, SQLAlchemyEngine)
    assert isinstance(engine, EngineCatalog)
    assert isinstance(engine, QueryEngine)


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_invalid_engine() -> None:
    """Test SQLAlchemyEngine with an invalid engine and inspector does not raise errors."""

    engine = SQLAlchemyEngine(connection=None, engine_name=None)  # type: ignore
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
    assert table.source_type == "connection"
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
def test_sqlalchemy_skip_meta_schemas(
    sqlite_engine_meta: sa.Engine,
) -> None:
    """Test SQLAlchemyEngine get_tables method."""
    engine = SQLAlchemyEngine(
        sqlite_engine_meta, engine_name=VariableName("test_sqlite")
    )
    databases = engine.get_databases(
        include_schemas=True, include_tables=True, include_table_details=True
    )
    assert len(databases[0].schemas) == 2
    assert databases[0].schemas[0].name == "main"
    assert databases[0].schemas[1].name == "information_schema"

    information_schema = databases[0].schemas[1]
    assert information_schema.tables == []


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_engine_get_schemas(sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine get_schemas method."""
    engine = SQLAlchemyEngine(
        sqlite_engine, engine_name=VariableName("test_sqlite")
    )
    schemas = engine.get_schemas(
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
    schemas = engine.get_schemas(
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
    schemas = engine.get_schemas(
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

    engine = SQLAlchemyEngine(
        sqlite_engine, engine_name=VariableName("test_sqlite")
    )
    result = engine.execute("SELECT * FROM test ORDER BY id")
    assert isinstance(result, (pd.DataFrame, pl.DataFrame))
    assert len(result) == 4


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_get_database_name(sqlite_engine: sa.Engine) -> None:
    """Test SQLAlchemyEngine get_database_name."""
    engine = SQLAlchemyEngine(
        sqlite_engine, engine_name=VariableName("test_sqlite")
    )
    assert engine.get_default_database() == ":memory:"

    import sqlalchemy as sa

    # Test with no database name
    engine = SQLAlchemyEngine(
        sa.create_engine("sqlite:///"), engine_name=VariableName("test_sqlite")
    )
    assert engine.get_default_database() == ""


@pytest.mark.skipif(
    not HAS_SQLALCHEMY or not HAS_POLARS or not HAS_PANDAS,
    reason="SQLAlchemy, Polars, and Pandas not installed",
)
def test_sqlalchemy_engine_sql_output_formats(
    sqlite_engine: sa.Engine,
) -> None:
    """Test SQLAlchemyEngine execute with different SQL output formats."""
    from unittest import mock

    import pandas as pd
    import polars as pl

    # Test with polars output format
    with mock.patch.object(
        SQLAlchemyEngine, "sql_output_format", return_value="polars"
    ):
        engine = SQLAlchemyEngine(
            sqlite_engine, engine_name=VariableName("test_sqlite")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, pl.DataFrame)
        assert len(result) == 4

    # Test with lazy-polars output format
    with mock.patch.object(
        SQLAlchemyEngine, "sql_output_format", return_value="lazy-polars"
    ):
        engine = SQLAlchemyEngine(
            sqlite_engine, engine_name=VariableName("test_sqlite")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, pl.LazyFrame)
        assert len(result.collect()) == 4

    # Test with pandas output format
    with mock.patch.object(
        SQLAlchemyEngine, "sql_output_format", return_value="pandas"
    ):
        engine = SQLAlchemyEngine(
            sqlite_engine, engine_name=VariableName("test_sqlite")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 4

    # Test with native output format
    with mock.patch.object(
        SQLAlchemyEngine, "sql_output_format", return_value="native"
    ):
        engine = SQLAlchemyEngine(
            sqlite_engine, engine_name=VariableName("test_sqlite")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert not isinstance(
            result, (pd.DataFrame, pl.DataFrame, pl.LazyFrame)
        )
        assert hasattr(result, "fetchall")

    # Test with auto output format (should use polars if available)
    with mock.patch.object(
        SQLAlchemyEngine, "sql_output_format", return_value="auto"
    ):
        engine = SQLAlchemyEngine(
            sqlite_engine, engine_name=VariableName("test_sqlite")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, (pd.DataFrame, pl.DataFrame))
        assert len(result) == 4


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_sqlalchemy_engine_get_cursor_metadata(
    sqlite_engine: sa.Engine,
) -> None:
    """Test SQLAlchemyEngine get_cursor_metadata."""
    from sqlalchemy.engine import CursorResult

    with mock.patch.object(
        SQLAlchemyEngine, "sql_output_format", return_value="native"
    ):
        engine = SQLAlchemyEngine(
            sqlite_engine, engine_name=VariableName("test_sqlite")
        )
        result = engine.execute("SELECT * FROM test ORDER BY id")
        assert isinstance(result, CursorResult)

        assert SQLAlchemyEngine.is_cursor_result(result)
        metadata = SQLAlchemyEngine.get_cursor_metadata(result)
        assert metadata is not None
        assert metadata["sql_statement_type"] == "Query / Unknown"


# ------------------------
# Decoracotors
# ------------------------


def test_returns_function_result_on_success():
    @safe_execute(fallback=None)
    def add(a, b):
        return a + b

    assert add(1, 2) == 3


def test_returns_fallback_on_exception():
    @safe_execute(fallback="oops")
    def fail():
        raise ValueError("boom")

    assert fail() == "oops"


@mock.patch("marimo._sql.engines.sqlalchemy.LOGGER")
def test_logs_on_exception(mock_logger):
    @safe_execute(
        fallback=None, message="something broke", log_level="warning"
    )
    def fail():
        raise TypeError("bad type")

    fail()

    mock_logger.warning.assert_called_once_with(
        "something broke", exc_info=True
    )


@mock.patch("marimo._sql.engines.sqlalchemy.LOGGER")
def test_respects_log_level_debug(mock_logger):
    @safe_execute(fallback=None, message="debug msg", log_level="debug")
    def fail():
        raise RuntimeError

    fail()

    mock_logger.debug.assert_called_once_with("debug msg", exc_info=True)


@mock.patch("marimo._sql.engines.sqlalchemy.LOGGER")
def test_respects_log_level_error(mock_logger):
    @safe_execute(fallback=None, message="error msg", log_level="error")
    def fail():
        raise RuntimeError

    fail()

    mock_logger.error.assert_called_once_with("error msg", exc_info=True)


@mock.patch("marimo._sql.engines.sqlalchemy.LOGGER")
def test_silent_exceptions_no_logging(mock_logger):
    @safe_execute(
        fallback=[],
        silent_exceptions=(NotImplementedError,),
    )
    def fail():
        raise NotImplementedError

    result = fail()

    assert result == []
    mock_logger.warning.assert_not_called()
    mock_logger.debug.assert_not_called()
    mock_logger.error.assert_not_called()
    mock_logger.info.assert_not_called()


@mock.patch("marimo._sql.engines.sqlalchemy.LOGGER")
def test_silent_exceptions_still_logs_other_errors(mock_logger):
    @safe_execute(
        fallback=-1,
        message="caught",
        log_level="error",
        silent_exceptions=(NotImplementedError,),
    )
    def fail():
        raise ValueError("not silent")

    result = fail()

    assert result == -1
    mock_logger.error.assert_called_once_with("caught", exc_info=True)


def test_preserves_function_metadata():
    @safe_execute(fallback=None)
    def my_func():
        """My docstring."""

    assert my_func.__name__ == "my_func"
    assert my_func.__doc__ == "My docstring."


def test_passes_args_and_kwargs():
    @safe_execute(fallback=None)
    def greet(name, greeting="Hello"):
        return f"{greeting}, {name}!"

    assert greet("Alice") == "Hello, Alice!"
    assert greet("Bob", greeting="Hi") == "Hi, Bob!"


def test_fallback_can_be_any_type():
    for fallback in (0, False, "", [], {}):

        @safe_execute(fallback=fallback)
        def fail():
            raise RuntimeError

        assert fail() == fallback


# ------------------------
# Tests for inspector methods
# ------------------------


@pytest.fixture
def make_engine():
    """Factory to create a SQLAlchemyEngine with a mocked Snowflake inspector."""

    def _factory(
        *,
        dialect="snowflake",
        default_database="MY_DB",
        schema_names=None,
        table_names=None,
        view_names=None,
        table_columns=None,
        columns=None,
        rows=None,
        pk_constraint=None,
        indexes=None,
        inspector=True,
    ):
        if columns is None:
            columns = [
                "created_on",
                "name",
                "is_default",
                "is_current",
                "origin",
            ]
        if rows is None:
            rows = []

        # -- Mock query results --
        mock_result = mock.MagicMock()
        mock_result.keys.return_value = columns
        mock_result.fetchall.return_value = rows

        mock_conn = mock.MagicMock()
        mock_conn.execute.return_value = mock_result

        # -- Mock inspector --
        mock_inspector = None
        if inspector:
            mock_inspector = mock.MagicMock()
            mock_inspector.get_schema_names.return_value = schema_names or []
            mock_inspector.get_table_names.return_value = table_names or []
            mock_inspector.get_view_names.return_value = view_names or []
            mock_inspector.get_columns.return_value = table_columns or []
            mock_inspector.get_pk_constraint.return_value = pk_constraint or {
                "constrained_columns": []
            }
            mock_inspector.get_indexes.return_value = indexes or []

        # -- Mock SQLAlchemy engine --
        mock_sa_engine = mock.MagicMock()
        mock_sa_engine.dialect.name = dialect
        mock_sa_engine.url.database = default_database
        mock_sa_engine.connect.return_value = mock.MagicMock(
            __enter__=mock.MagicMock(return_value=mock_conn),
            __exit__=mock.MagicMock(return_value=False),
        )

        # Patch inspect() so __init__ assigns our configured mock
        with mock.patch("sqlalchemy.inspect", return_value=mock_inspector):
            engine = SQLAlchemyEngine(
                mock_sa_engine, engine_name=VariableName("test")
            )

        # Point _connection to the mock so execute() calls work
        engine._connection = mock_sa_engine

        # Override _get_inspector to yield our mock inspector.
        # Uses *_args, **_kwargs to match any signature the real
        # method may have (e.g. database parameter) without
        # global side effects.
        @contextmanager
        def fake_get_inspector(database=None):
            _ = database  # ignore parameter
            yield mock_inspector

        engine._get_inspector = fake_get_inspector

        # Expose mocks for test assertions
        engine._mock_inspector = mock_inspector
        engine._mock_conn = mock_conn

        return engine

    return _factory


# ------------------------------------------------------------------ #
#  _get_inspector
# ------------------------------------------------------------------ #


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_get_inspector_executes_use_database():
    """executes dialect command and inspects the connection."""
    mock_conn = mock.MagicMock()
    mock_command = mock.MagicMock()

    mock_sa_engine = mock.MagicMock()
    mock_sa_engine.dialect.name = "snowflake"
    mock_sa_engine.url.database = "MY_DB"
    mock_sa_engine.connect.return_value.__enter__ = mock.MagicMock(
        return_value=mock_conn
    )
    mock_sa_engine.connect.return_value.__exit__ = mock.MagicMock(
        return_value=False
    )

    engine = SQLAlchemyEngine(mock_sa_engine, engine_name=VariableName("test"))

    with (
        mock.patch(
            "sqlalchemy.inspect", return_value=mock_command
        ) as patched_inspect,
        engine._get_inspector("my_db") as inspector,
    ):
        assert inspector is mock_command
        patched_inspect.assert_called_once_with(mock_conn)

    # Verify USE DATABASE was executed
    executed = mock_conn.execute.call_args[0][0]
    assert str(executed) == "USE DATABASE my_db"

    with (
        mock.patch(
            "sqlalchemy.inspect", return_value=mock_command
        ) as patched_inspect,
        engine._get_inspector("MY_DB@MYDB") as inspector,
    ):
        assert inspector is mock_command
        patched_inspect.assert_called_once_with(mock_conn)

    # Verify USE DATABASE was executed
    executed = mock_conn.execute.call_args[0][0]
    assert str(executed) == 'USE DATABASE "MY_DB@MYDB"'

    with (
        mock.patch(
            "sqlalchemy.inspect", return_value=mock_command
        ) as patched_inspect,
        engine._get_inspector("MY_db") as inspector,
    ):
        assert inspector is mock_command
        patched_inspect.assert_called_once_with(mock_conn)

    # Verify USE DATABASE was executed
    executed = mock_conn.execute.call_args[0][0]
    assert str(executed) == 'USE DATABASE "MY_db"'


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_get_inspector_yields_existing_inspector_for_non_use_database_dialect():
    """For dialects without USE DATABASE, yield self.inspector directly."""
    mock_sa_engine = mock.MagicMock()
    mock_sa_engine.dialect.name = "sqlite"
    mock_sa_engine.url.database = ":memory:"

    engine = SQLAlchemyEngine(mock_sa_engine, engine_name=VariableName("test"))

    mock_inspector = mock.MagicMock()
    engine.inspector = mock_inspector

    with engine._get_inspector("any_database") as inspector:
        assert inspector is mock_inspector

    # Verify that NO connection was opened and no command was executed
    mock_sa_engine.connect.assert_not_called()


# ------------------------------------------------------------------ #
#  _get_schema_names
# ------------------------------------------------------------------ #


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_get_schema_names(make_engine):
    engine = make_engine(schema_names=["public", "staging"])
    assert engine._get_schema_names("MY_DB") == ["public", "staging"]


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_get_schema_names_no_inspector(make_engine):
    engine = make_engine(inspector=False)
    assert engine._get_schema_names("MY_DB") == []


# ------------------------------------------------------------------ #
#  _get_table_names
# ------------------------------------------------------------------ #


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_get_table_names(make_engine):
    engine = make_engine(
        table_names=["users", "orders"], view_names=["active_users"]
    )
    tables, views = engine._get_table_names(schema="public", database="MY_DB")
    assert tables == ["users", "orders"]
    assert views == ["active_users"]


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_get_table_names_no_inspector(make_engine):
    engine = make_engine(inspector=False)
    assert engine._get_table_names(schema="public", database="MY_DB") == (
        [],
        [],
    )


# ------------------------------------------------------------------ #
#  _get_columns
# ------------------------------------------------------------------ #


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_get_columns(make_engine):
    cols = [
        {"name": "id", "type": "INTEGER"},
        {"name": "name", "type": "TEXT"},
    ]
    engine = make_engine(table_columns=cols)
    result = engine._get_columns("users", schema="public", database="MY_DB")
    assert result == cols


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_get_columns_no_inspector(make_engine):
    engine = make_engine(inspector=False)
    assert (
        engine._get_columns("users", schema="public", database="MY_DB") is None
    )


# ------------------------------------------------------------------ #
#  _fetch_primary_keys
# ------------------------------------------------------------------ #


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_fetch_primary_keys(make_engine):
    engine = make_engine(
        pk_constraint={"constrained_columns": ["id", "tenant_id"]}
    )
    result = engine._fetch_primary_keys(
        "users", schema="public", database="MY_DB"
    )
    assert result == ["id", "tenant_id"]


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_fetch_primary_keys_no_inspector(make_engine):
    engine = make_engine(inspector=False)
    result = engine._fetch_primary_keys(
        "users", schema="public", database="MY_DB"
    )
    assert result == []


# ------------------------------------------------------------------ #
#  _fetch_indexes
# ------------------------------------------------------------------ #


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_fetch_indexes(make_engine):
    engine = make_engine(
        indexes=[
            {"column_names": ["email"], "name": "idx_email", "unique": True},
            {"column_names": ["name"], "name": "idx_name", "unique": False},
        ]
    )
    result = engine._fetch_indexes("users", schema="public", database="MY_DB")
    assert result == ["email", "name"]


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_fetch_indexes_no_inspector(make_engine):
    engine = make_engine(inspector=False)
    result = engine._fetch_indexes("users", schema="public", database="MY_DB")
    assert result == []


# ------------------------------------------------------------------ #
#  _extract_index_columns (static, no mocking needed)
# ------------------------------------------------------------------ #


def test_extract_index_columns_deduplicates():
    indexes = [
        {"column_names": ["col_a", "col_b"]},
        {"column_names": ["col_b", "col_c"]},
    ]
    assert SQLAlchemyEngine._extract_index_columns(indexes) == [
        "col_a",
        "col_b",
        "col_c",
    ]


def test_extract_index_columns_skips_none():
    indexes = [{"column_names": [None, "col_a", None]}]
    assert SQLAlchemyEngine._extract_index_columns(indexes) == ["col_a"]


def test_extract_index_columns_missing_key():
    indexes = [{"name": "idx"}, {"column_names": ["col_a"]}]
    assert SQLAlchemyEngine._extract_index_columns(indexes) == ["col_a"]


def test_extract_index_columns_empty():
    assert SQLAlchemyEngine._extract_index_columns([]) == []


# ---------------------------------
# Snowflake-specific GET databases
# ---------------------------------


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_snowflake_returns_all_in_lower_case_when_no_default(make_engine):
    engine = make_engine(
        default_database=None,
        rows=[
            ("2025-01-01", "DB_A", "N", "N", ""),
            ("2025-01-02", "DB_B", "N", "N", ""),
        ],
    )
    assert engine._get_snowflake_database_names() == ["db_a", "db_b"]


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_snowflake_returns_only_default_when_present(make_engine):
    engine = make_engine(
        default_database="db_B",
        rows=[
            ("2025-01-01", "DB_A", "N", "N", ""),
            ("2025-01-02", "DB_B", "N", "Y", ""),
        ],
    )
    assert engine._get_snowflake_database_names() == ["db_b"]


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_get_snowflake_database_names_lowercases_unless_special_characters(
    make_engine,
):
    engine = make_engine(
        default_database=None,
        rows=[
            ("2025-01-01", "DB_A", "N", "N", ""),
            ("2025-01-02", "DB_B", "N", "Y", ""),
            ("2025-01-02", "USER@snow", "N", "Y", ""),
        ],
    )
    assert engine._get_snowflake_database_names() == [
        "db_a",
        "db_b",
        "USER@snow",
    ]


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_snowflake_returns_all_when_default_not_in_results(make_engine):
    engine = make_engine(
        default_database="MISSING",
        rows=[
            ("2025-01-01", "DB_A", "N", "N", ""),
            ("2025-01-02", "DB_B", "N", "Y", ""),
        ],
    )
    assert engine._get_snowflake_database_names() == ["db_a", "db_b"]


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_snowflake_returns_empty_list_when_no_rows(make_engine):
    engine = make_engine(rows=[])
    assert engine._get_snowflake_database_names() == []


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_snowflake_raises_when_name_column_missing(make_engine):
    engine = make_engine(columns=["id", "owner", "comment"])
    with pytest.raises(RuntimeError, match="'name' column not found"):
        engine._get_snowflake_database_names()


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_snowflake_executes_show_databases(make_engine):
    engine = make_engine()
    engine._get_snowflake_database_names()
    executed_sql = engine._mock_conn.execute.call_args[0][0]
    assert str(executed_sql) == "SHOW DATABASES"


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_snowflake_name_column_at_different_index(make_engine):
    engine = make_engine(
        columns=["id", "owner", "name"],
        rows=[(1, "ADMIN", "MY_DB")],
    )
    assert engine._get_snowflake_database_names() == ["my_db"]


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_snowflake_database_names_coerced_to_str(make_engine):
    engine = make_engine(columns=["name"], rows=[(123,), (456,)])
    assert engine._get_snowflake_database_names() == ["123", "456"]


@pytest.mark.skipif(not HAS_SQLALCHEMY, reason="SQLAlchemy not installed")
def test_snowflake_get_database_names_delegates(make_engine):
    """Snowflake dialect delegates to _get_snowflake_database_names."""
    engine = make_engine(default_database="MY_DB")

    expected = ["DB_A", "DB_B"]
    with mock.patch.object(
        engine, "_get_snowflake_database_names", return_value=expected
    ) as mocked:
        result = engine._get_database_names()

    mocked.assert_called_once()
    assert result == expected
