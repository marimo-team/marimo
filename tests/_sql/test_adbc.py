# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import pytest

from marimo._data.models import Database, DataTable, Schema
from marimo._sql.engines.adbc import (
    AdbcConnectionCatalog,
    AdbcDBAPIEngine,
    _adbc_info_to_dialect,
)
from marimo._sql.get_engines import get_engines_from_variables
from marimo._types.ids import VariableName

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    import pyarrow as pa


@dataclass
class FakeAdbcSchemaField:
    name: str
    type: str


class FakeAdbcTableSchema:
    def __init__(self, fields: list[FakeAdbcSchemaField]) -> None:
        self._fields = fields

    def __iter__(self) -> Iterator[FakeAdbcSchemaField]:
        return iter(self._fields)


class FakeAdbcObjectsTable:
    def __init__(self, pylist: list[dict[str, Any]]) -> None:
        self._pylist = pylist

    def to_pylist(self) -> list[dict[str, Any]]:
        return self._pylist


class FakeAdbcObjectsReader:
    def __init__(self, pylist: list[dict[str, Any]]) -> None:
        self._table = FakeAdbcObjectsTable(pylist)

    def read_all(self) -> FakeAdbcObjectsTable:
        return self._table


class FakeAdbcDbApiCursor:
    def __init__(
        self,
        *,
        description: list[tuple[str, Any]] | None,
        arrow_table: pa.Table | None = None,
    ) -> None:
        self.description = description
        self._arrow_table: pa.Table | None = arrow_table
        self.did_execute = False
        self.did_fetch_arrow = False
        self.did_close = False

    def execute(
        self, query: str, parameters: Sequence[Any] = ()
    ) -> FakeAdbcDbApiCursor:
        _ = query, parameters
        self.did_execute = True
        return self

    def fetch_arrow_table(self) -> pa.Table:
        self.did_fetch_arrow = True
        assert self._arrow_table is not None
        return self._arrow_table

    def close(self) -> None:
        self.did_close = True


class FakeAdbcDbApiConnection:
    adbc_current_catalog: str
    adbc_current_db_schema: str

    def __init__(
        self,
        *,
        cursor: FakeAdbcDbApiCursor,
        objects_pylist: list[dict[str, Any]],
        table_schema: FakeAdbcTableSchema,
    ) -> None:
        self._cursor = cursor
        self._objects_pylist = objects_pylist
        self._table_schema = table_schema
        self.did_commit = False
        self.did_rollback = False
        self.did_close = False
        self.dialect = "postgresql"
        self.adbc_current_catalog = "db1"
        self.adbc_current_db_schema = "public"
        self.did_create_cursor = False
        self.last_get_objects_kwargs: dict[str, Any] | None = None
        self.adbc_get_info_calls = 0

    def cursor(self) -> FakeAdbcDbApiCursor:
        self.did_create_cursor = True
        return self._cursor

    def commit(self) -> None:
        self.did_commit = True

    def rollback(self) -> None:
        self.did_rollback = True

    def close(self) -> None:
        self.did_close = True

    # ADBC DB-API extension methods
    def adbc_get_objects(
        self,
        *,
        depth: str = "all",
        catalog_filter: str | None = None,
        db_schema_filter: str | None = None,
        table_name_filter: str | None = None,
        table_types_filter: list[str] | None = None,
        column_name_filter: str | None = None,
    ) -> pa.RecordBatchReader:
        self.last_get_objects_kwargs = {
            "depth": depth,
            "catalog_filter": catalog_filter,
            "db_schema_filter": db_schema_filter,
            "table_name_filter": table_name_filter,
            "table_types_filter": table_types_filter,
            "column_name_filter": column_name_filter,
        }

        catalogs: list[dict[str, Any]] = []
        for catalog_row in self._objects_pylist:
            catalog_name_obj = catalog_row.get("catalog_name")
            catalog_name = (
                "" if catalog_name_obj is None else str(catalog_name_obj)
            )
            if catalog_filter is not None and catalog_name != catalog_filter:
                continue

            next_catalog_row: dict[str, Any] = dict(catalog_row)
            if depth == "catalogs":
                next_catalog_row["catalog_db_schemas"] = []
                catalogs.append(next_catalog_row)
                continue

            schemas = catalog_row.get("catalog_db_schemas") or []
            next_schemas: list[dict[str, Any]] = []
            for schema_row in schemas:
                schema_name_obj = schema_row.get("db_schema_name")
                schema_name = (
                    "" if schema_name_obj is None else str(schema_name_obj)
                )
                if (
                    db_schema_filter is not None
                    and schema_name != db_schema_filter
                ):
                    continue

                next_schema_row: dict[str, Any] = dict(schema_row)
                if depth == "db_schemas":
                    next_schema_row["db_schema_tables"] = []
                    next_schemas.append(next_schema_row)
                    continue

                tables = schema_row.get("db_schema_tables") or []
                next_tables: list[dict[str, Any]] = []
                for table_row in tables:
                    table_name_obj = table_row.get("table_name")
                    if table_name_obj is None:
                        continue
                    table_name = str(table_name_obj)
                    if (
                        table_name_filter is not None
                        and table_name != table_name_filter
                    ):
                        continue

                    table_type_obj = table_row.get("table_type")
                    table_type = (
                        "" if table_type_obj is None else str(table_type_obj)
                    )
                    if (
                        table_types_filter is not None
                        and table_type not in table_types_filter
                    ):
                        continue

                    next_tables.append(dict(table_row))

                next_schema_row["db_schema_tables"] = next_tables
                next_schemas.append(next_schema_row)

            next_catalog_row["catalog_db_schemas"] = next_schemas
            catalogs.append(next_catalog_row)

        # ADBC DB-API wrapper returns a pyarrow.RecordBatchReader; our fake
        # emulates the reader's `read_all().to_pylist()` interface.
        return cast(Any, FakeAdbcObjectsReader(catalogs))

    def adbc_get_table_schema(
        self, table_name: str, *, db_schema_filter: str | None = None
    ) -> pa.Schema:
        _ = table_name, db_schema_filter
        return cast(Any, self._table_schema)

    def adbc_get_info(self) -> dict[str | int, Any]:
        self.adbc_get_info_calls += 1
        return cast(dict[str | int, Any], {"vendor_name": "PostgreSQL"})


def test_adbc_info_to_dialect() -> None:
    # Vendor string is lowercased (and stripped); driver_name is ignored.
    assert (
        _adbc_info_to_dialect(
            info={"vendor_name": "PostgreSQL", "driver_name": "SQLite"}
        )
        == "postgresql"
    )
    assert (
        _adbc_info_to_dialect(info={"vendor_name": "Microsoft SQL Server"})
        == "microsoft sql server"
    )

    # Missing/blank/non-string vendor_name falls back to "sql".
    assert _adbc_info_to_dialect(info={"vendor_name": "   "}) == "sql"
    assert _adbc_info_to_dialect(info={"vendor_name": 123}) == "sql"
    assert _adbc_info_to_dialect(info={"driver_name": "AcmeDB"}) == "sql"
    assert _adbc_info_to_dialect(info={}) == "sql"


def test_get_engines_from_variables_prefers_adbc_dbapi_engine() -> None:
    conn = FakeAdbcDbApiConnection(
        cursor=FakeAdbcDbApiCursor(description=None),
        objects_pylist=[],
        table_schema=FakeAdbcTableSchema([]),
    )

    engines = get_engines_from_variables([(VariableName("conn"), conn)])
    assert len(engines) == 1
    _, engine = engines[0]
    assert isinstance(engine, AdbcDBAPIEngine)


def test_adbc_catalog_parses_adbc_get_objects() -> None:
    objects_pylist = [
        {
            "catalog_name": "db1",
            "catalog_db_schemas": [
                {
                    "db_schema_name": "public",
                    "db_schema_tables": [
                        {"table_name": "t1", "table_type": "TABLE"},
                        {"table_name": "v1", "table_type": "VIEW"},
                    ],
                }
            ],
        }
    ]
    conn = FakeAdbcDbApiConnection(
        cursor=FakeAdbcDbApiCursor(description=None),
        objects_pylist=objects_pylist,
        table_schema=FakeAdbcTableSchema(
            [
                FakeAdbcSchemaField(name="id", type="int64"),
                FakeAdbcSchemaField(name="name", type="utf8"),
            ]
        ),
    )

    engine = AdbcDBAPIEngine(conn, engine_name=VariableName("adbc_conn"))
    databases = engine.get_databases(
        include_schemas=True,
        include_tables=True,
        include_table_details=False,
    )
    assert conn.last_get_objects_kwargs is not None
    assert conn.last_get_objects_kwargs["depth"] == "tables"

    assert databases == [
        Database(
            name="db1",
            dialect="postgresql",
            engine=VariableName("adbc_conn"),
            schemas=[
                Schema(
                    name="public",
                    tables=[
                        DataTable(
                            source_type="connection",
                            source="postgresql",
                            name="t1",
                            num_rows=None,
                            num_columns=None,
                            variable_name=None,
                            engine=VariableName("adbc_conn"),
                            type="table",
                            columns=[],
                            primary_keys=[],
                            indexes=[],
                        ),
                        DataTable(
                            source_type="connection",
                            source="postgresql",
                            name="v1",
                            num_rows=None,
                            num_columns=None,
                            variable_name=None,
                            engine=VariableName("adbc_conn"),
                            type="view",
                            columns=[],
                            primary_keys=[],
                            indexes=[],
                        ),
                    ],
                )
            ],
        )
    ]


def test_adbc_execute_prefers_arrow_fetch(monkeypatch) -> None:
    sentinel_result = object()

    def fake_convert_to_output(*args: Any, **kwargs: Any) -> Any:
        _ = args, kwargs
        return sentinel_result

    monkeypatch.setattr(
        "marimo._sql.engines.adbc.convert_to_output", fake_convert_to_output
    )

    cursor = FakeAdbcDbApiCursor(
        description=[("col", None)],
        arrow_table=cast("pa.Table", object()),
    )
    conn = FakeAdbcDbApiConnection(
        cursor=cursor,
        objects_pylist=[],
        table_schema=FakeAdbcTableSchema([]),
    )
    engine = AdbcDBAPIEngine(conn)

    monkeypatch.setattr(engine, "sql_output_format", lambda: "auto")
    result = engine.execute("SELECT 1")

    assert result is sentinel_result
    assert cursor.did_fetch_arrow is True
    assert conn.did_commit is True
    assert cursor.did_close is True


def test_adbc_execute_native_returns_arrow_table(monkeypatch) -> None:
    arrow_table = cast("pa.Table", object())
    cursor = FakeAdbcDbApiCursor(
        description=[("col", None)], arrow_table=arrow_table
    )
    conn = FakeAdbcDbApiConnection(
        cursor=cursor,
        objects_pylist=[],
        table_schema=FakeAdbcTableSchema([]),
    )
    engine = AdbcDBAPIEngine(conn)

    monkeypatch.setattr(engine, "sql_output_format", lambda: "native")
    result = engine.execute("SELECT 1")

    assert result is arrow_table
    assert cursor.did_execute is True
    assert cursor.did_fetch_arrow is True
    assert conn.did_commit is True
    assert cursor.did_close is True


def test_adbc_is_compatible_does_not_create_cursor() -> None:
    conn = FakeAdbcDbApiConnection(
        cursor=FakeAdbcDbApiCursor(description=None),
        objects_pylist=[],
        table_schema=FakeAdbcTableSchema([]),
    )
    # is_compatible() validates cursor shape; it should not execute or fetch.
    assert AdbcDBAPIEngine.is_compatible(conn) is True
    assert conn.did_create_cursor is True
    assert conn._cursor.did_execute is False  # type: ignore[attr-defined]
    assert conn._cursor.did_fetch_arrow is False  # type: ignore[attr-defined]
    assert conn._cursor.did_close is True  # type: ignore[attr-defined]


def test_adbc_catalog_auto_discovery_uses_cheap_dialect_heuristic() -> None:
    conn = FakeAdbcDbApiConnection(
        cursor=FakeAdbcDbApiCursor(description=None),
        objects_pylist=[],
        table_schema=FakeAdbcTableSchema([]),
    )
    cheap = AdbcConnectionCatalog(
        adbc_connection=conn,
        dialect="sqlite",
        engine_name=None,
    )
    assert cheap._resolve_should_auto_discover("auto") is True
    assert cheap._resolve_should_auto_discover(True) is True
    assert cheap._resolve_should_auto_discover(False) is False

    expensive = AdbcConnectionCatalog(
        adbc_connection=conn,
        dialect="snowflake",
        engine_name=None,
    )
    assert expensive._resolve_should_auto_discover("auto") is False


def test_adbc_catalog_get_databases_uses_depth_catalogs_when_no_schemas() -> (
    None
):
    conn = FakeAdbcDbApiConnection(
        cursor=FakeAdbcDbApiCursor(description=None),
        objects_pylist=[
            {
                "catalog_name": "db1",
                "catalog_db_schemas": [
                    {"db_schema_name": "public", "db_schema_tables": []}
                ],
            },
            {"catalog_name": "db2", "catalog_db_schemas": []},
        ],
        table_schema=FakeAdbcTableSchema([]),
    )
    engine = AdbcDBAPIEngine(conn)
    databases = engine.get_databases(
        include_schemas=False,
        include_tables=True,
        include_table_details=True,
    )
    assert conn.last_get_objects_kwargs is not None
    assert conn.last_get_objects_kwargs["depth"] == "catalogs"
    assert [db.name for db in databases] == ["db1", "db2"]
    assert [db.schemas for db in databases] == [[], []]


def test_adbc_catalog_get_databases_uses_depth_db_schemas_when_no_tables() -> (
    None
):
    conn = FakeAdbcDbApiConnection(
        cursor=FakeAdbcDbApiCursor(description=None),
        objects_pylist=[
            {
                "catalog_name": "db1",
                "catalog_db_schemas": [
                    {"db_schema_name": "public", "db_schema_tables": []},
                    {"db_schema_name": "empty", "db_schema_tables": []},
                ],
            }
        ],
        table_schema=FakeAdbcTableSchema([]),
    )
    engine = AdbcDBAPIEngine(conn)
    databases = engine.get_databases(
        include_schemas=True,
        include_tables=False,
        include_table_details=False,
    )
    assert conn.last_get_objects_kwargs is not None
    assert conn.last_get_objects_kwargs["depth"] == "db_schemas"
    assert [s.name for s in databases[0].schemas] == ["public", "empty"]
    assert [s.tables for s in databases[0].schemas] == [[], []]


def test_adbc_get_tables_in_schema_passes_filters() -> None:
    conn = FakeAdbcDbApiConnection(
        cursor=FakeAdbcDbApiCursor(description=None),
        objects_pylist=[
            {
                "catalog_name": "db1",
                "catalog_db_schemas": [
                    {
                        "db_schema_name": "public",
                        "db_schema_tables": [
                            {"table_name": "t1", "table_type": "TABLE"}
                        ],
                    },
                    {
                        "db_schema_name": "other",
                        "db_schema_tables": [
                            {"table_name": "t2", "table_type": "TABLE"}
                        ],
                    },
                ],
            },
            {
                "catalog_name": "db2",
                "catalog_db_schemas": [
                    {
                        "db_schema_name": "public",
                        "db_schema_tables": [
                            {"table_name": "t3", "table_type": "TABLE"}
                        ],
                    }
                ],
            },
        ],
        table_schema=FakeAdbcTableSchema([]),
    )
    engine = AdbcDBAPIEngine(conn)
    tables = engine.get_tables_in_schema(
        schema="public", database="db1", include_table_details=False
    )
    assert conn.last_get_objects_kwargs is not None
    assert conn.last_get_objects_kwargs["depth"] == "tables"
    assert conn.last_get_objects_kwargs["catalog_filter"] == "db1"
    assert conn.last_get_objects_kwargs["db_schema_filter"] == "public"
    assert [t.name for t in tables] == ["t1"]


def _find_table_location(
    *, databases: list[Any], table_name: str
) -> tuple[str, str]:
    for db in databases:
        for schema in db.schemas:
            for table in schema.tables:
                if table.name == table_name:
                    return db.name, schema.name
    raise AssertionError(f"Did not find table {table_name!r} in catalog")


def _table_summary(table: DataTable) -> dict[str, Any]:
    """Return a stable representation of a DataTable for assertions."""
    return {
        "name": table.name,
        "type": table.type,
        "num_columns": table.num_columns,
        "column_names": [c.name for c in table.columns],
        "column_types": {c.name: c.type for c in table.columns},
    }


def test_adbc_sqlite_driver_catalog_interface() -> None:
    """Smoke test marimo ADBC catalog interface against the real SQLite driver."""
    pytest.importorskip(
        "pyarrow", reason="ADBC DBAPI wrapper requires PyArrow"
    )
    adbc_sqlite_dbapi = pytest.importorskip("adbc_driver_sqlite.dbapi")

    conn: Any = adbc_sqlite_dbapi.connect()
    try:
        engine = AdbcDBAPIEngine(conn)
        assert engine.source == "adbc"
        assert engine.dialect == "sqlite"
        assert AdbcDBAPIEngine.is_compatible(conn) is True

        # Minimal schema for catalog discovery.
        cursor = conn.cursor()
        try:
            cursor.execute("CREATE TABLE t (id INTEGER, name TEXT)")
            cursor.execute("CREATE TABLE t2 (x REAL)")
            cursor.execute(
                """
                CREATE TABLE t_types (
                    int_col INTEGER,
                    real_col REAL,
                    text_col TEXT,
                    blob_col BLOB,
                    bool_col BOOLEAN,
                    date_col DATE,
                    time_col TIME,
                    ts_col TIMESTAMP,
                    numeric_col NUMERIC
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO t_types (
                    int_col,
                    real_col,
                    text_col,
                    blob_col,
                    bool_col,
                    date_col,
                    time_col,
                    ts_col,
                    numeric_col
                ) VALUES (
                    1,
                    1.5,
                    'hello',
                    X'0001',
                    1,
                    '2026-01-04',
                    '12:34:56',
                    '2026-01-04 12:34:56',
                    123.45
                )
                """
            )
            conn.commit()
        finally:
            cursor.close()

        # Default database/schema should be readable (may be None on SQLite).
        _ = engine.get_default_database()
        _ = engine.get_default_schema()

        # When schemas are excluded, we should not return any schema information.
        dbs = engine.get_databases(
            include_schemas=False,
            include_tables=True,
            include_table_details=True,
        )
        assert all(db.schemas == [] for db in dbs)

        # When tables are excluded, we should not return any tables.
        dbs = engine.get_databases(
            include_schemas=True,
            include_tables=False,
            include_table_details=True,
        )
        assert all(
            all(schema.tables == [] for schema in db.schemas) for db in dbs
        )

        # When table details are excluded, tables should have no columns.
        dbs = engine.get_databases(
            include_schemas=True,
            include_tables=True,
            include_table_details=False,
        )
        db_name, schema_name = _find_table_location(
            databases=dbs, table_name="t"
        )
        db_name_types, schema_name_types = _find_table_location(
            databases=dbs, table_name="t_types"
        )
        t_no_details = next(
            t
            for db in dbs
            for schema in db.schemas
            for t in schema.tables
            if db.name == db_name
            and schema.name == schema_name
            and t.name == "t"
        )
        assert _table_summary(t_no_details) == {
            "name": "t",
            "type": "table",
            "num_columns": None,
            "column_names": [],
            "column_types": {},
        }
        t_types_no_details = next(
            t
            for db in dbs
            for schema in db.schemas
            for t in schema.tables
            if db.name == db_name_types
            and schema.name == schema_name_types
            and t.name == "t_types"
        )
        assert _table_summary(t_types_no_details) == {
            "name": "t_types",
            "type": "table",
            "num_columns": None,
            "column_names": [],
            "column_types": {},
        }

        # With details enabled, columns should be populated.
        dbs = engine.get_databases(
            include_schemas=True,
            include_tables=True,
            include_table_details=True,
        )
        t_with_details = next(
            t
            for db in dbs
            for schema in db.schemas
            for t in schema.tables
            if db.name == db_name
            and schema.name == schema_name
            and t.name == "t"
        )
        t_summary = _table_summary(t_with_details)
        assert {
            "name": t_summary["name"],
            "type": t_summary["type"],
            "num_columns": t_summary["num_columns"],
            "column_names": t_summary["column_names"],
        } == {
            "name": "t",
            "type": "table",
            "num_columns": 2,
            "column_names": ["id", "name"],
        }
        assert t_summary["column_types"]["id"] == "integer"
        # SQLite/driver-specific: "name TEXT" may be mapped inconsistently.
        assert t_summary["column_types"]["name"] in ("string", "integer")

        t_types_with_details = next(
            t
            for db in dbs
            for schema in db.schemas
            for t in schema.tables
            if db.name == db_name_types
            and schema.name == schema_name_types
            and t.name == "t_types"
        )
        types_summary = _table_summary(t_types_with_details)
        assert types_summary["name"] == "t_types"
        assert types_summary["type"] == "table"
        assert types_summary["num_columns"] == 9
        assert set(types_summary["column_names"]) == {
            "int_col",
            "real_col",
            "text_col",
            "blob_col",
            "bool_col",
            "date_col",
            "time_col",
            "ts_col",
            "numeric_col",
        }

        # Verify that the driver/schema mapping yields sensible marimo DataTypes.
        col_types = cast(dict[str, str], types_summary["column_types"])
        assert col_types["int_col"] == "integer"
        assert col_types["real_col"] == "number"
        assert col_types["text_col"] == "string"
        # SQLite/driver-specific: these may come back as strings/ints depending on
        # how the driver maps SQLite affinities.
        assert col_types["bool_col"] in ("boolean", "integer")
        assert col_types["date_col"] in ("date", "string")
        assert col_types["time_col"] in ("time", "string")
        assert col_types["ts_col"] in ("datetime", "string")
        assert col_types["numeric_col"] in ("number", "integer", "string")

        tables = engine.get_tables_in_schema(
            schema=schema_name, database=db_name, include_table_details=False
        )
        assert {t.name for t in tables} >= {"t", "t2", "t_types"}

        tables_with_details = engine.get_tables_in_schema(
            schema=schema_name, database=db_name, include_table_details=True
        )
        t = next(t for t in tables_with_details if t.name == "t")
        assert {c.name for c in t.columns} == {"id", "name"}
        t_types = next(t for t in tables_with_details if t.name == "t_types")
        assert {c.name for c in t_types.columns} == {
            "int_col",
            "real_col",
            "text_col",
            "blob_col",
            "bool_col",
            "date_col",
            "time_col",
            "ts_col",
            "numeric_col",
        }
    finally:
        conn.close()


def test_adbc_sqlite_driver_execute_polars(monkeypatch) -> None:
    """Smoke test marimo ADBC engine against the real ADBC SQLite driver."""
    pytest.importorskip(
        "pyarrow", reason="ADBC DBAPI wrapper requires PyArrow"
    )
    pl = pytest.importorskip("polars")
    adbc_sqlite_dbapi = pytest.importorskip("adbc_driver_sqlite.dbapi")

    conn: Any = adbc_sqlite_dbapi.connect()
    try:
        engine = AdbcDBAPIEngine(conn)
        assert engine.source == "adbc"
        assert engine.dialect == "sqlite"
        assert AdbcDBAPIEngine.is_compatible(conn) is True

        engine.execute("CREATE TABLE t (id INTEGER)")
        engine.execute("INSERT INTO t VALUES (1), (2)")

        from marimo._sql.get_engines import engine_to_data_source_connection

        # Ensure we can produce a DataSourceConnection for the UI/kernel message path.
        connection = engine_to_data_source_connection(
            VariableName("adbc_sqlite"), engine
        )
        assert connection.source == "adbc"
        assert connection.dialect == "sqlite"
        assert connection.name == "adbc_sqlite"
        assert "sqlite" in connection.display_name.lower()

        monkeypatch.setattr(engine, "sql_output_format", lambda: "polars")
        df = engine.execute("SELECT id FROM t ORDER BY id")
        assert isinstance(df, pl.DataFrame)
        assert df.to_dicts() == [{"id": 1}, {"id": 2}]
    finally:
        conn.close()
