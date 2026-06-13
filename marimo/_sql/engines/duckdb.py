# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from typing import TYPE_CHECKING, Any, Literal, Optional, cast

from marimo import _loggers
from marimo._data.get_datasets import get_databases_from_duckdb
from marimo._data.models import (
    CatalogNode,
    Database,
    DataTable,
    Namespace,
    Schema,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.context.types import (
    ContextNotInitializedError,
    get_context,
)
from marimo._sql.engines.types import InferenceConfig, SQLConnection
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
            import polars as pl

            # `lazy=True` requires DuckDB >= 1.4 and pyarrow. Fall back to the
            # Arrow PyCapsule path on older DuckDB or when pyarrow is missing.
            # batch_size of 100k bounds peak memory at ~10x less than DuckDB's
            # 1M default while keeping per-batch overhead negligible.
            try:
                return cast(
                    pl.LazyFrame,
                    cast(Any, relation).pl(batch_size=100_000, lazy=True),
                )
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
        # At the moment this isn't being used for duckdb
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
        """Fetch all databases from the engine. At the moment, will fetch everything."""
        _, _, _ = include_schemas, include_tables, include_table_details
        import duckdb

        connection = cast(
            duckdb.DuckDBPyConnection, self._connection or duckdb
        )
        with self._install_connection(connection):
            return get_databases_from_duckdb(connection, self._engine_name)

    def get_catalog_children(
        self,
        *,
        database: str,
        catalog_path: list[str],
        include_table_details: bool,
    ) -> list[CatalogNode]:
        """Return DuckDB catalog children from the existing full-tree loader."""
        del include_table_details
        databases = self.get_databases(
            include_schemas=True,
            include_tables=True,
            include_table_details=False,
        )
        selected_database = next(
            (db for db in databases if db.name == database), None
        )
        if selected_database is None:
            return []
        if not catalog_path:
            return selected_database.children

        nodes = selected_database.children
        for index, segment in enumerate(catalog_path):
            node = next(
                (
                    candidate
                    for candidate in nodes
                    if candidate.name == segment
                ),
                None,
            )
            if node is None:
                return []
            if index == len(catalog_path) - 1:
                if isinstance(node, Schema):
                    return [*node.tables]
                if isinstance(node, Namespace):
                    return node.children
                return []
            if not isinstance(node, Namespace):
                return []
            nodes = node.children
        return []

    # TODO: The following methods are currently not implemented.
    # We should consider implementing these in the future for better performance when users don't want to fetch everything.
    def get_schemas(
        self,
        *,
        database: str | None,
        include_tables: bool,
        include_table_details: bool,
        schema_path: list[str] | None = None,
    ) -> list[CatalogNode]:
        """Get all schemas and optionally their tables. Keys are schema names."""
        _, _, _, _ = (
            database,
            include_tables,
            include_table_details,
            schema_path,
        )
        return []

    def get_tables_in_schema(
        self,
        *,
        schema: str,
        database: str,
        include_table_details: bool,
        schema_path: list[str] | None = None,
    ) -> list[DataTable]:
        """Return all tables in a schema. This is currently implemented in get_databases_from_duckdb."""
        _, _, _, _ = database, schema, include_table_details, schema_path
        return []

    def get_table_details(
        self,
        *,
        table_name: str,
        schema_name: str,
        database_name: str,
        schema_path: list[str] | None = None,
    ) -> DataTable | None:
        """Get a single table from the engine. This is currently implemented in get_databases_from_duckdb."""
        _, _, _, _ = table_name, schema_name, database_name, schema_path
        return None
