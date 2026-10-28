# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Optional, cast

from marimo import _loggers
from marimo._data.get_datasets import _db_type_to_data_type, get_table_columns
from marimo._data.models import (
    Database,
    DataTable,
    DataTableColumn,
    DataTableType,
    Schema,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.context.types import (
    ContextNotInitializedError,
    get_context,
)
from marimo._sql.engines.types import InferenceConfig, SQLConnection
from marimo._sql.sql_quoting import quote_qualified_name
from marimo._sql.utils import convert_to_output, is_duckdb_v2, wrapped_sql
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Iterator

    import duckdb
    import polars as pl

# Internal engine names
INTERNAL_DUCKDB_ENGINE = cast(VariableName, "__marimo_duckdb")


@dataclass(frozen=True)
class _CatalogSchema:
    """DuckDB schema metadata with an OID and ordered path within a database."""

    database: str
    oid: int
    path: tuple[str, ...]


class DuckDBEngine(SQLConnection[Optional["duckdb.DuckDBPyConnection"]]):
    """DuckDB SQL engine."""

    def __init__(
        self,
        connection: duckdb.DuckDBPyConnection | None = None,
        engine_name: VariableName | None = None,
    ) -> None:
        super().__init__(connection, engine_name)

    @contextmanager
    def _install_connection(
        self, connection: duckdb.DuckDBPyConnection
    ) -> Iterator[None]:
        try:
            ctx = get_context()
        except ContextNotInitializedError:
            execution_context = None
        else:
            execution_context = ctx.execution_context
        mgr = (
            execution_context.with_connection
            if execution_context is not None
            else nullcontext
        )
        with mgr(connection):
            yield

    @property
    def source(self) -> str:
        return "duckdb"

    @property
    def dialect(self) -> str:
        return "duckdb"

    @staticmethod
    def execute_and_return_relation(
        query: str, params: list[Any] | None = None
    ) -> duckdb.DuckDBPyRelation | None:
        """Execute a query and return a relation. Supports parameters."""
        DependencyManager.duckdb.require("to execute sql")

        import duckdb

        return duckdb.sql(query, params=params)

    def execute(self, query: str) -> Any:
        relation = wrapped_sql(query, self._connection)

        # Invalid / empty query
        if relation is None:
            return None

        sql_output_format = self.sql_output_format()

        def to_polars() -> pl.DataFrame:
            import polars as pl

            # Use the Arrow PyCapsule interface (pl.DataFrame(relation))
            # instead of relation.pl() so that pyarrow is not required.
            return pl.DataFrame(relation)

        def to_lazy_polars() -> pl.LazyFrame:
            # `lazy=True` requires DuckDB >= 1.4 and pyarrow. Fall back to the
            # Arrow PyCapsule path on older DuckDB or when pyarrow is missing.
            # batch_size of 100k bounds peak memory at ~10x less than DuckDB's
            # 1M default while keeping per-batch overhead negligible.
            import polars as pl

            try:
                result = relation.pl(batch_size=100_000, lazy=True)
            except (TypeError, ImportError, ModuleNotFoundError):
                return to_polars().lazy()
            if not isinstance(result, pl.LazyFrame):
                raise TypeError(
                    "DuckDB did not return a lazy Polars DataFrame"
                )
            return result

        return convert_to_output(
            sql_output_format=sql_output_format,
            to_polars=to_polars,
            to_pandas=lambda: relation.df(),
            to_native=lambda: relation,
            to_lazy_polars=to_lazy_polars,
        )

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.duckdb.imported():
            return False

        import duckdb

        return isinstance(var, duckdb.DuckDBPyConnection)

    @property
    def inference_config(self) -> InferenceConfig:
        return InferenceConfig(
            auto_discover_schemas=True,
            auto_discover_tables="auto",
            auto_discover_columns=False,
        )

    def get_default_database(self) -> str | None:
        try:
            import duckdb

            connection = cast(
                duckdb.DuckDBPyConnection, self._connection or duckdb
            )
            with self._install_connection(connection):
                rows = connection.sql("SELECT CURRENT_DATABASE()").fetchall()
            row = rows[0] if rows else None
            if row is not None and row[0] is not None:
                return str(row[0])
            return None
        except Exception:
            LOGGER.info("Failed to get current database")
            return None

    def get_default_schema(self) -> str | None:
        try:
            import duckdb

            connection = cast(
                duckdb.DuckDBPyConnection, self._connection or duckdb
            )
            with self._install_connection(connection):
                rows = connection.sql("SELECT CURRENT_SCHEMA()").fetchall()
            row = rows[0] if rows else None
            if row is not None and row[0] is not None:
                return str(row[0])
            return None
        except Exception:
            LOGGER.info("Failed to get current schema")
            return None

    def get_databases(
        self,
        *,
        include_schemas: bool | Literal["auto"],
        include_tables: bool | Literal["auto"],
        include_table_details: bool | Literal["auto"],
    ) -> list[Database]:
        """List databases, discovering only the requested metadata depth."""
        schemas_resolved = self._resolve_should_auto_discover(include_schemas)
        tables_resolved = self._resolve_should_auto_discover(include_tables)
        details_resolved = self._resolve_should_auto_discover(
            include_table_details
        )
        # Keep the temporary catalog accessible without scanning its tables.
        rows = self._query_catalog(
            "SELECT database_name FROM duckdb_databases() "
            "WHERE NOT internal OR database_name = 'temp' "
            "ORDER BY database_name"
        )
        databases = {
            name: Database(
                name=name,
                dialect=self.dialect,
                engine=self._engine_name,
                schemas_resolved=schemas_resolved,
                schemas=[],
            )
            for (name,) in rows
        }
        if schemas_resolved and databases:
            schemas = self._get_catalog_schemas()
            for database in databases.values():
                database.schemas = self._make_schemas(
                    [
                        schema
                        for schema in schemas
                        if schema.database == database.name
                    ],
                    include_tables=tables_resolved,
                    include_table_details=False,
                )
            if details_resolved:
                self._load_table_details(
                    {
                        (database.name, path, table.name): table
                        for database in databases.values()
                        for path, table in self._schema_tables(
                            database.schemas
                        )
                    },
                    schemas=schemas,
                )
        return list(databases.values())

    def _query_catalog(
        self, query: str, params: list[Any] | None = None
    ) -> list[Any]:
        import duckdb

        connection = cast(
            duckdb.DuckDBPyConnection, self._connection or duckdb
        )
        try:
            with self._install_connection(connection):
                return connection.execute(query, params).fetchall()
        except duckdb.ConnectionException:
            LOGGER.debug("Skipping closed DuckDB connection")
            return []

    def _get_catalog_schemas(
        self, database: str | None = None
    ) -> list[_CatalogSchema]:
        parent_column = "parent_schema_oid" if is_duckdb_v2() else "NULL"
        query = (
            "SELECT database_name, oid, schema_name, "
            f"{parent_column} FROM duckdb_schemas() "
            "WHERE NOT (internal AND schema_name IN ('information_schema', 'pg_catalog'))"
        )
        params = None
        if database is not None:
            query += " AND database_name = ?"
            params = [database]
        rows = self._query_catalog(
            query + " ORDER BY database_name, schema_name", params
        )
        names = {(db, oid): (name, parent) for db, oid, name, parent in rows}

        def schema_path(database: str, oid: int) -> tuple[str, ...]:
            name, parent = names[database, oid]
            if parent is None:
                return (name,)
            return (*schema_path(database, parent), name)

        return [
            _CatalogSchema(db, oid, schema_path(db, oid))
            for db, oid, _, _ in rows
        ]

    def get_schemas(
        self,
        *,
        database: str | None,
        include_tables: bool,
        include_table_details: bool,
        schema_path: list[str] | None = None,
    ) -> list[Schema]:
        """List immediate schemas, preserving deferred table discovery."""
        database = (
            database if database is not None else self.get_default_database()
        )
        if database is None:
            return []
        schemas = self._get_catalog_schemas(database)
        result = self._make_schemas(
            schemas,
            parent_path=tuple(schema_path or ()),
            include_tables=include_tables,
            include_table_details=False,
        )
        if include_tables and include_table_details:
            self._load_table_details(
                {
                    (database, path, table.name): table
                    for path, table in self._schema_tables(
                        result, tuple(schema_path or ())
                    )
                },
                schemas=schemas,
                database=database,
                schema_oids={
                    schema.oid
                    for schema in schemas
                    if schema.path[: len(schema_path or ())]
                    == tuple(schema_path or ())
                },
            )
        return result

    def _make_schemas(
        self,
        schemas: list[_CatalogSchema],
        *,
        parent_path: tuple[str, ...] = (),
        include_tables: bool,
        include_table_details: bool,
    ) -> list[Schema]:
        children: dict[tuple[str, ...], list[_CatalogSchema]] = {}
        for schema in schemas:
            children.setdefault(schema.path[:-1], []).append(schema)

        def build(path: tuple[str, ...]) -> list[Schema]:
            return [
                Schema(
                    name=schema.path[-1],
                    tables=self._get_schema_tables(
                        schema, include_table_details=include_table_details
                    )
                    if include_tables
                    else [],
                    tables_resolved=include_tables,
                    child_schemas=build(schema.path) if include_tables else [],
                    child_schemas_resolved=include_tables
                    or schema.path not in children,
                )
                for schema in children.get(path, [])
            ]

        return build(parent_path)

    @staticmethod
    def _schema_tables(
        schemas: list[Schema], parent_path: tuple[str, ...] = ()
    ) -> Iterator[tuple[tuple[str, ...], DataTable]]:
        for schema in schemas:
            path = (*parent_path, schema.name)
            for table in schema.tables:
                yield path, table
            yield from DuckDBEngine._schema_tables(schema.child_schemas, path)

    def _find_schema(
        self, database: str, path: tuple[str, ...]
    ) -> _CatalogSchema | None:
        normalized_path = tuple(part.lower() for part in path)
        return next(
            (
                schema
                for schema in self._get_catalog_schemas(database)
                if tuple(part.lower() for part in schema.path)
                == normalized_path
            ),
            None,
        )

    def _table_rows(
        self, schema: _CatalogSchema, table_name: str | None = None
    ) -> list[tuple[str, DataTableType]]:
        predicate = "NOT internal AND database_name = ? AND schema_oid = ?"
        params: list[str | int] = [schema.database, schema.oid]
        if table_name is not None:
            predicate += " AND table_name = ?"
            params.append(table_name)
        return self._query_catalog(
            f"SELECT table_name, 'table' FROM duckdb_tables() WHERE {predicate} "
            f"UNION ALL SELECT view_name, 'view' FROM duckdb_views() WHERE "
            + predicate.replace("table_name", "view_name")
            + " ORDER BY 1",
            params * 2,
        )

    def _get_schema_tables(
        self, schema: _CatalogSchema, *, include_table_details: bool
    ) -> list[DataTable]:
        tables = {
            (schema.database, schema.path, name): self._make_table(
                name, schema.database, table_type=kind
            )
            for name, kind in self._table_rows(schema)
        }
        if include_table_details:
            self._load_table_details(
                tables,
                schemas=[schema],
                database=schema.database,
                schema_oids={schema.oid},
            )
        return list(tables.values())

    def get_tables_in_schema(
        self,
        *,
        schema: str,
        database: str,
        include_table_details: bool,
        schema_path: list[str] | None = None,
    ) -> list[DataTable]:
        """List tables and views in a schema, optionally loading their columns."""
        catalog_schema = self._find_schema(
            database, tuple(schema_path or [schema])
        )
        if catalog_schema is None:
            return []
        return self._get_schema_tables(
            catalog_schema, include_table_details=include_table_details
        )

    def _load_table_details(
        self,
        tables: dict[tuple[str, tuple[str, ...], str], DataTable],
        *,
        schemas: list[_CatalogSchema],
        database: str | None = None,
        schema_oids: set[int] | None = None,
    ) -> None:
        if not tables:
            return
        paths = {
            (schema.database, schema.oid): schema.path for schema in schemas
        }
        query = (
            "SELECT database_name, schema_oid, table_name, column_name, data_type "
            "FROM duckdb_columns() WHERE NOT internal"
        )
        params: list[str | int] = []
        if database is not None:
            query += " AND database_name = ?"
            params.append(database)
        if schema_oids is not None:
            if not schema_oids:
                return
            query += (
                " AND schema_oid IN ("
                + ", ".join("?" for _ in schema_oids)
                + ")"
            )
            params.extend(sorted(schema_oids))
        query += (
            " ORDER BY database_name, schema_oid, table_name, column_index"
        )
        try:
            rows = self._query_catalog(query, params)
        except Exception:
            LOGGER.warning("Failed to get DuckDB columns", exc_info=True)
            return
        for db_name, oid, table_name, column_name, dtype in rows:
            path = paths.get((db_name, oid))
            if path is None:
                continue
            table = tables.get((db_name, path, table_name))
            if table is not None:
                table.columns.append(
                    DataTableColumn(
                        name=column_name,
                        type=_db_type_to_data_type(dtype),
                        external_type=dtype,
                        sample_values=[],
                    )
                )
        for (_, path, _), table in tables.items():
            # Some Iceberg catalogs expose a placeholder instead of columns.
            if len(table.columns) == 1 and table.columns[0].name == "__":
                table.columns = []
                self._describe_table(table, path)
            if table.columns:
                table.num_columns = len(table.columns)

    def _make_table(
        self, name: str, database: str, *, table_type: DataTableType = "table"
    ) -> DataTable:
        return DataTable(
            source_type="duckdb"
            if self._engine_name is None
            else "connection",
            source=database,
            name=name,
            type=table_type,
            num_rows=None,
            num_columns=None,
            variable_name=None,
            columns=[],
            engine=self._engine_name,
        )

    def get_table_details(
        self,
        *,
        table_name: str,
        schema_name: str,
        database_name: str,
        schema_path: list[str] | None = None,
    ) -> DataTable | None:
        """Describe only the requested table, including remote catalog tables."""
        path = tuple(schema_path or [schema_name])
        schema = self._find_schema(database_name, path)
        if schema is None:
            return None
        rows = self._table_rows(schema, table_name)
        if not rows:
            return None
        table = self._make_table(
            table_name, database_name, table_type=rows[0][1]
        )
        self._describe_table(table, path)
        return table if table.columns else None

    def _describe_table(
        self, table: DataTable, schema_path: tuple[str, ...]
    ) -> None:
        import duckdb

        connection = cast(
            duckdb.DuckDBPyConnection, self._connection or duckdb
        )
        qualified_name = quote_qualified_name(
            table.source, *schema_path, table.name
        )
        with self._install_connection(connection):
            table.columns = get_table_columns(connection, qualified_name)
        if table.columns:
            table.num_columns = len(table.columns)
