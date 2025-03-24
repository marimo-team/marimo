# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, cast

from marimo import _loggers
from marimo._data.get_datasets import get_databases_from_duckdb
from marimo._data.models import Database
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.types import SQLEngine
from marimo._sql.utils import raise_df_import_error, wrapped_sql
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    import duckdb

# Internal engine names
INTERNAL_DUCKDB_ENGINE = cast(VariableName, "__marimo_duckdb")


class DuckDBEngine(SQLEngine):
    """DuckDB SQL engine."""

    def __init__(
        self,
        connection: Optional[duckdb.DuckDBPyConnection] = None,
        engine_name: Optional[VariableName] = None,
    ) -> None:
        self._connection = connection
        self._engine_name = engine_name

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

        if DependencyManager.polars.has():
            return relation.pl()
        elif DependencyManager.pandas.has():
            return relation.df()
        else:
            raise_df_import_error("polars[pyarrow]")

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.duckdb.imported():
            return False

        import duckdb

        return isinstance(var, duckdb.DuckDBPyConnection)

    def get_current_database(self) -> Optional[str]:
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

    def get_current_schema(self) -> Optional[str]:
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

    def get_databases(self) -> list[Database]:
        """Fetch all databases from the engine. At the moment, will fetch everything."""
        return get_databases_from_duckdb(self._connection, self._engine_name)
