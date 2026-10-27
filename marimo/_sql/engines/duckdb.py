# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager, nullcontext
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
from marimo._sql.utils import convert_to_output, wrapped_sql
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Iterator

    import duckdb
    import polars as pl

# Internal engine names
INTERNAL_DUCKDB_ENGINE = cast(VariableName, "__marimo_duckdb")


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
    ) -> duckdb.DuckDBPyRelation:
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
            try:
                return relation.pl(batch_size=100_000, lazy=True)
            except (TypeError, ImportError, ModuleNotFoundError):
                return to_polars().lazy()

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
                row = connection.sql("SELECT CURRENT_DATABASE()").fetchone()
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
                row = connection.sql("SELECT CURRENT_SCHEMA()").fetchone()
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
            # duckdb_schemas() scans every catalog before applying filters.
            # Query it once so remote namespaces are not fetched per database.
            schema_rows = self._query_catalog(
                "SELECT database_name, schema_name FROM duckdb_schemas() "
                "WHERE schema_name NOT IN ('information_schema', 'pg_catalog') "
                "ORDER BY database_name, schema_name"
            )
            for database_name, schema_name in schema_rows:
                if database_name in databases:
                    databases[database_name].schemas.append(
                        self._make_schema(
                            schema_name,
                            database_name,
                            include_tables=tables_resolved,
                            include_table_details=False,
                        )
                    )
        if details_resolved:
            self._load_table_details(
                {
                    (database.name, schema.name, table.name): table
                    for database in databases.values()
                    for schema in database.schemas
                    for table in schema.tables
                }
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

    def get_schemas(
        self,
        *,
        database: str | None,
        include_tables: bool,
        include_table_details: bool,
        schema_path: list[str] | None = None,
    ) -> list[Schema]:
        """List schemas without enumerating tables unless requested."""
        if schema_path:
            return []
        if database is None:
            database = self.get_default_database()
        if database is None:
            return []
        rows = self._query_catalog(
            "SELECT schema_name FROM duckdb_schemas() "
            "WHERE database_name = ? "
            "AND schema_name NOT IN ('information_schema', 'pg_catalog') "
            "ORDER BY schema_name",
            [database],
        )
        return [
            self._make_schema(
                name,
                database,
                include_tables=include_tables,
                include_table_details=include_table_details,
            )
            for (name,) in rows
        ]

    def _make_schema(
        self,
        name: str,
        database: str,
        *,
        include_tables: bool,
        include_table_details: bool,
    ) -> Schema:
        tables = []
        if include_tables:
            tables = self.get_tables_in_schema(
                schema=name,
                database=database,
                include_table_details=include_table_details,
            )
        return Schema(name=name, tables=tables, tables_resolved=include_tables)

    def get_tables_in_schema(
        self,
        *,
        schema: str,
        database: str,
        include_table_details: bool,
        schema_path: list[str] | None = None,
    ) -> list[DataTable]:
        """List table and view names without eagerly loading their columns."""
        del schema_path
        rows = self._query_catalog(
            "SELECT table_name, table_type FROM information_schema.tables "
            "WHERE table_catalog = ? AND table_schema = ? ORDER BY table_name",
            [database, schema],
        )
        tables = {
            (database, schema, name): self._make_table(
                name,
                database,
                table_type="view" if kind == "VIEW" else "table",
            )
            for name, kind in rows
        }
        if include_table_details:
            self._load_table_details(tables, database=database, schema=schema)
        return list(tables.values())

    def _load_table_details(
        self,
        tables: dict[tuple[str, str, str], DataTable],
        *,
        database: str | None = None,
        schema: str | None = None,
    ) -> None:
        if not tables:
            return
        query = (
            "SELECT database_name, schema_name, table_name, column_name, data_type "
            "FROM duckdb_columns() WHERE NOT internal"
        )
        params: list[str] = []
        if database is not None:
            query += " AND database_name = ?"
            params.append(database)
        if schema is not None:
            query += " AND schema_name = ?"
            params.append(schema)
        query += (
            " ORDER BY database_name, schema_name, table_name, column_index"
        )
        try:
            rows = self._query_catalog(query, params)
        except Exception:
            # A metadata failure must not hide tables already enumerated.
            LOGGER.warning("Failed to get DuckDB columns", exc_info=True)
            return
        for db_name, schema_name, table_name, column_name, dtype in rows:
            table = tables.get((db_name, schema_name, table_name))
            if table is not None:
                table.columns.append(
                    DataTableColumn(
                        name=column_name,
                        type=_db_type_to_data_type(dtype),
                        external_type=dtype,
                        sample_values=[],
                    )
                )
        for (_, schema_name, _), table in tables.items():
            # Some Iceberg catalogs expose a placeholder instead of columns.
            if len(table.columns) == 1 and table.columns[0].name == "__":
                table.columns = []
                self._describe_table(table, schema_name)
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
        del schema_path
        rows = self._query_catalog(
            "SELECT table_type FROM information_schema.tables "
            "WHERE table_catalog = ? AND table_schema = ? AND table_name = ?",
            [database_name, schema_name, table_name],
        )
        if not rows:
            return None
        table = self._make_table(
            table_name,
            database_name,
            table_type="view" if rows[0][0] == "VIEW" else "table",
        )
        self._describe_table(table, schema_name)
        return table if table.columns else None

    def _describe_table(self, table: DataTable, schema: str) -> None:
        import duckdb

        connection = cast(
            duckdb.DuckDBPyConnection, self._connection or duckdb
        )
        qualified_name = quote_qualified_name(table.source, schema, table.name)
        with self._install_connection(connection):
            table.columns = get_table_columns(connection, qualified_name)
        if table.columns:
            table.num_columns = len(table.columns)
