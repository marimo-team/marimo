# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from marimo import _loggers
from marimo._data.get_datasets import get_datasets_from_duckdb
from marimo._data.models import DataTable, DataTableColumn, DataType
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.types import SQLEngine
from marimo._sql.utils import wrapped_sql

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    import duckdb
    from sqlalchemy import Engine


def raise_df_import_error(pkg: str) -> None:
    raise ModuleNotFoundError(
        "pandas or polars is required to execute sql. "
        + "You can install them with 'pip install pandas polars'",
        name=pkg,
    )


class DuckDBEngine(SQLEngine):
    """DuckDB SQL engine."""

    def __init__(
        self,
        connection: Optional[duckdb.DuckDBPyConnection],
        engine_name: Optional[str] = None,
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
            raise_df_import_error("polars")

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.duckdb.imported():
            return False

        import duckdb

        return isinstance(var, duckdb.DuckDBPyConnection)

    def get_tables(self) -> list[DataTable]:
        return get_datasets_from_duckdb(self._connection, self._engine_name)


class SQLAlchemyEngine(SQLEngine):
    """SQLAlchemy engine."""

    def __init__(
        self, engine: Engine, engine_name: Optional[str] = None
    ) -> None:
        self._engine = engine
        self._engine_name = engine_name

    @property
    def source(self) -> str:
        return str(self._engine.dialect.name)

    @property
    def dialect(self) -> str:
        return str(self._engine.dialect.name)

    def execute(self, query: str) -> Any:
        # Can't use polars.imported() because this is the first time we
        # might come across polars.
        if not (
            DependencyManager.polars.has() or DependencyManager.pandas.has()
        ):
            raise_df_import_error("polars")

        from sqlalchemy import text

        with self._engine.connect() as connection:
            result = connection.execute(text(query))
            connection.commit()

        if not result.returns_rows:
            return None

        if DependencyManager.polars.has():
            import polars as pl

            return pl.DataFrame(result)  # type: ignore
        else:
            import pandas as pd

            return pd.DataFrame(result)

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.sqlalchemy.imported():
            return False

        from sqlalchemy.engine import Engine

        return isinstance(var, Engine)

    def _should_include_columns(self) -> bool:
        # Including columns can fan out to a lot of requests,
        # so this is disabled for now.
        # Maybe in future we can enable this as a flag or for certain connection types.
        return False

    def get_tables(self) -> list[DataTable]:
        from sqlalchemy import MetaData

        try:
            metadata = MetaData()
            metadata.reflect(bind=self._engine)
        except Exception:
            LOGGER.debug("Failed to reflect tables", exc_info=True)
            # If we fail to reflect, we don't want to crash the app.
            # Just return an empty list.
            return []

        tables: list[DataTable] = []
        for table_name, table in metadata.tables.items():
            tables.append(
                DataTable(
                    source_type="connection",
                    source=self.dialect,
                    name=table_name,
                    num_rows=None,
                    num_columns=len(table.columns),
                    variable_name=None,
                    engine=self._engine_name,
                    columns=(
                        [
                            DataTableColumn(
                                name=col.name,
                                type=_sql_type_to_data_type(str(col.type)),
                                external_type=str(col.type),
                                sample_values=[],
                            )
                            for col in table.columns
                        ]
                    ),
                )
            )
        return tables


def _sql_type_to_data_type(type_str: str) -> DataType:
    """Convert SQL type string to DataType"""
    type_str = type_str.lower()
    if any(x in type_str for x in ("int", "serial")):
        return "integer"
    elif any(x in type_str for x in ("float", "double", "decimal", "numeric")):
        return "number"
    elif any(x in type_str for x in ("timestamp", "datetime")):
        return "datetime"
    elif "date" in type_str:
        return "date"
    elif "bool" in type_str:
        return "boolean"
    elif any(x in type_str for x in ("char", "text")):
        return "string"
    else:
        return "string"
