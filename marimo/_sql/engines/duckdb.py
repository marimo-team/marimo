# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from typing import TYPE_CHECKING, Any, Literal, Optional, Union, cast

from marimo import _loggers
from marimo._data.get_datasets import get_databases_from_duckdb
from marimo._data.models import Database, DataTable
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

# Internal engine names
INTERNAL_DUCKDB_ENGINE = cast(VariableName, "__marimo_duckdb")


class DuckDBEngine(SQLConnection[Optional["duckdb.DuckDBPyConnection"]]):
    """DuckDB SQL engine."""

    def __init__(
        self,
        connection: Optional[duckdb.DuckDBPyConnection] = None,
        engine_name: Optional[VariableName] = None,
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
        query: str, params: Optional[list[Any]] = None
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

        return convert_to_output(
            sql_output_format=sql_output_format,
            to_polars=lambda: relation.pl(),
            to_pandas=lambda: relation.df(),
            to_native=lambda: relation,
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

    def get_default_database(self) -> Optional[str]:
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

    def get_default_schema(self) -> Optional[str]:
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
        include_schemas: Union[bool, Literal["auto"]],
        include_tables: Union[bool, Literal["auto"]],
        include_table_details: Union[bool, Literal["auto"]],
    ) -> list[Database]:
        """Fetch all databases from the engine. At the moment, will fetch everything."""
        _, _, _ = include_schemas, include_tables, include_table_details
        import duckdb

        connection = cast(
            duckdb.DuckDBPyConnection, self._connection or duckdb
        )
        with self._install_connection(connection):
            return get_databases_from_duckdb(connection, self._engine_name)

    def get_tables_in_schema(
        self, *, schema: str, database: str, include_table_details: bool
    ) -> list[DataTable]:
        """Return all tables in a schema. This is currently implemented in get_databases_from_duckdb."""
        _, _, _ = database, schema, include_table_details
        return []

    def get_table_details(
        self, *, table_name: str, schema_name: str, database_name: str
    ) -> Optional[DataTable]:
        """Get a single table from the engine. This is currently implemented in get_databases_from_duckdb."""
        _, _, _ = table_name, schema_name, database_name
        return None
