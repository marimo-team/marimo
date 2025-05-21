# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Optional, Union, cast

from marimo import _loggers
from marimo._data.get_datasets import get_databases_from_duckdb
from marimo._data.models import Database, DataTable
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.types import (
    InferenceConfig,
    SQLConnection,
    register_engine,
)
from marimo._sql.utils import raise_df_import_error, wrapped_sql
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    import duckdb

# Internal engine names
INTERNAL_DUCKDB_ENGINE = cast(VariableName, "__marimo_duckdb")


@register_engine
class DuckDBEngine(SQLConnection[Optional["duckdb.DuckDBPyConnection"]]):
    """DuckDB SQL engine."""

    def __init__(
        self,
        connection: Optional[duckdb.DuckDBPyConnection] = None,
        engine_name: Optional[VariableName] = None,
    ) -> None:
        super().__init__(connection, engine_name)

    @property
    def source(self) -> str:
        return "duckdb"

    @property
    def dialect(self) -> str:
        return "duckdb"

    def execute(self, query: str) -> Any:
        relation = wrapped_sql(query, self._connection)

        # Invalid / empty query
        if relation is None:
            return None

        sql_output_format = self.sql_output_format()
        if sql_output_format == "polars":
            return relation.pl()
        if sql_output_format == "lazy-polars":
            return relation.pl().lazy()
        if sql_output_format == "native":
            return relation
        if sql_output_format == "pandas":
            return relation.df()

        # Auto
        if DependencyManager.polars.has():
            import polars as pl

            try:
                return relation.pl()
            except (
                pl.exceptions.PanicException,
                pl.exceptions.ComputeError,
            ) as e:
                LOGGER.warning("Failed to convert to polars. Reason: %s.", e)
                DependencyManager.pandas.require("to convert this data")

        if DependencyManager.pandas.has():
            try:
                return relation.df()
            except Exception as e:
                LOGGER.warning("Failed to convert dataframe", exc_info=e)
                return None

        raise_df_import_error("polars[pyarrow]")

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

            connection = self._connection or duckdb
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

            connection = self._connection or duckdb
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
        return get_databases_from_duckdb(self._connection, self._engine_name)

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
