# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from marimo import _loggers
from marimo._data.get_datasets import get_databases_from_duckdb
from marimo._data.models import (
    Database,
    DataTable,
    DataTableColumn,
    DataType,
    Schema,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.types import SQLEngine
from marimo._sql.utils import wrapped_sql
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    import duckdb
    from sqlalchemy import Engine
    from sqlalchemy.engine.reflection import Inspector
    from sqlalchemy.sql.type_api import TypeEngine


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
            raise_df_import_error("polars")

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.duckdb.imported():
            return False

        import duckdb

        return isinstance(var, duckdb.DuckDBPyConnection)

    def get_databases(
        self, include_schemas: bool, include_tables: bool
    ) -> list[Database]:
        return get_databases_from_duckdb(self._connection, self._engine_name)


class SQLAlchemyEngine(SQLEngine):
    """SQLAlchemy engine."""

    inspector: Inspector

    def __init__(
        self, engine: Engine, engine_name: Optional[VariableName] = None
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

    def get_databases(
        self, include_schemas: bool, include_tables: bool
    ) -> list[Database]:
        """Fetch all databases from the engine.

        Args:
            include_schemas: Whether to include schema information
            include_tables: Whether to include table information within schemas

        Returns:
            List of DatabaseCollection objects representing the database structure

        Note: This operation can be performance intensive when fetching full metadata.
        """
        from sqlalchemy import inspect

        # Initialize inspector once and store as instance variable, maybe move this to a func
        if not hasattr(self, "inspector"):
            self.inspector = inspect(self._engine)

        databases: list[Database] = []
        database_name = self._engine.url.database

        # No database specified - could add multi-database support in future
        if database_name is None:
            return []

        schemas = self.get_schemas(include_tables) if include_schemas else {}
        databases.append(
            Database(
                name=database_name,
                source=self.dialect,
                schemas=schemas,
                engine=self._engine_name,
            )
        )
        return databases

    def get_schemas(self, include_tables: bool) -> dict[str, Schema]:
        """Get all schemas and optionally their tables. Keys are schema names."""
        schema_names = self.inspector.get_schema_names()
        if not include_tables:
            return {
                schema: Schema(name=schema, tables={})
                for schema in schema_names
            }

        return {
            schema: Schema(
                name=schema,
                tables=self.get_tables_in_schema(schema),
            )
            for schema in schema_names
        }

    def get_tables_in_schema(self, schema: str) -> dict[str, DataTable]:
        """Return all tables in a schema. Keys are table names."""
        table_names = self.inspector.get_table_names(schema=schema)
        view_names = self.inspector.get_view_names(schema=schema)
        tables = [("table", name) for name in table_names] + [
            ("view", name) for name in view_names
        ]

        def get_python_type(col_type: TypeEngine) -> str | bool:
            try:
                col_type = col_type.python_type
                return _sql_type_to_data_type(str(col_type))
            except Exception:
                # LOGGER.debug("Failed to get python type", exc_info=True)
                return False

        def get_generic_type(col_type: TypeEngine) -> str | bool:
            try:
                col_type = col_type.as_generic()
                return _sql_type_to_data_type(str(col_type))
            except Exception:
                # LOGGER.debug("Failed to get generic type", exc_info=True)
                return False

        primary_keys: list[str] = []
        index_list: list[str] = []

        data_tables: dict[str, DataTable] = {}
        for t_type, t_name in tables:
            columns = self.inspector.get_columns(t_name, schema)
            indexes = self.inspector.get_indexes(t_name, schema)

            try:
                # TODO: investigate this
                index_list.extend(col["name"] for col in indexes)
            except Exception:
                pass

            cols: list[DataTableColumn] = []
            for col in columns:
                col_type = col["type"]
                col_type = (
                    get_python_type(col_type)
                    or get_generic_type(col_type)
                    or "string"
                )

                try:
                    if col["primary_key"]:
                        primary_keys.append(col["name"])
                except KeyError:
                    pass

                cols.append(
                    DataTableColumn(
                        name=col["name"],
                        type=col_type,
                        external_type=str(col["type"]),
                        sample_values=[],
                    )
                )

            data_tables[t_name] = DataTable(
                source_type="connection",
                source=self.dialect,
                name=t_name,
                num_rows=None,
                num_columns=len(columns),
                variable_name=None,
                engine=self._engine_name,
                columns=cols,
                type=t_type,
                primary_keys=primary_keys,
                indexes=indexes,
            )

        return data_tables

    def _reflect_tables(self) -> list[DataTable] | False:
        from sqlalchemy import MetaData

        try:
            metadata = MetaData()
            metadata.reflect(bind=self._engine)
        except Exception:
            LOGGER.debug("Failed to reflect tables", exc_info=True)
            return False

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
                    primary_keys=[table.primary_key.columns.keys()],
                    indexes=[],
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
