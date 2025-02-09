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

    def __init__(
        self, engine: Engine, engine_name: Optional[VariableName] = None
    ) -> None:
        from sqlalchemy import inspect

        self._engine = engine
        self._engine_name = engine_name
        self.inspector = inspect(self._engine)

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
        databases: list[Database] = []
        database_name = self._engine.url.database

        # No database specified - could add multi-database support in future
        if database_name is None:
            return []

        schemas = self.get_schemas(include_tables) if include_schemas else []
        databases.append(
            Database(
                name=database_name,
                source=self.dialect,
                schemas=schemas,
                engine=self._engine_name,
            )
        )
        return databases

    def get_schemas(self, include_tables: bool) -> list[Schema]:
        """Get all schemas and optionally their tables. Keys are schema names."""
        schema_names = self.inspector.get_schema_names()
        schemas: list[Schema] = []

        for schema in schema_names:
            schemas.append(
                Schema(
                    name=schema,
                    tables=self.get_tables_in_schema(schema)
                    if include_tables
                    else [],
                )
            )

        return schemas

    def get_tables_in_schema(
        self, schema: str, include_table_info: bool = True
    ) -> list[DataTable]:
        """Return all tables in a schema."""
        table_names = self.inspector.get_table_names(schema=schema)
        view_names = self.inspector.get_view_names(schema=schema)
        tables = [("table", name) for name in table_names] + [
            ("view", name) for name in view_names
        ]

        if not include_table_info:
            return [
                DataTable(name=name, type=table_type)
                for table_type, name in tables
            ]

        data_tables: list[DataTable] = []
        for t_type, t_name in tables:
            table = self.get_table(t_name, schema)
            if table is not None:
                table.type = t_type
                data_tables.append(table)

        return data_tables

    def get_table(
        self, table_name: str, schema_name: str
    ) -> Optional[DataTable]:
        """Get a single table from the engine."""
        try:
            columns = self.inspector.get_columns(
                table_name, schema=schema_name
            )
            indexes = self.inspector.get_indexes(
                table_name, schema=schema_name
            )
        except Exception:
            LOGGER.debug(
                f"Failed to get table {table_name} in schema {schema_name}",
                exc_info=True,
            )
            return None

        primary_keys: list[str] = []
        index_list: list[str] = []

        try:
            index_list.extend(col["name"] for col in indexes)
        except Exception:
            pass

        cols: list[DataTableColumn] = []
        for col in columns:
            col_type = col["type"]
            col_type = (
                self._get_python_type(col_type)
                or self._get_generic_type(col_type)
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

        return DataTable(
            source_type="connection",
            source=self.dialect,
            name=table_name,
            num_rows=None,
            num_columns=len(columns),
            variable_name=None,
            engine=self._engine_name,
            columns=cols,
            primary_keys=primary_keys,
            indexes=index_list,
        )

    def _get_python_type(self, col_type: TypeEngine) -> DataType | None:
        try:
            col_type = col_type.python_type
            return _sql_type_to_data_type(str(col_type))
        except AttributeError:
            LOGGER.debug(f"Python type not available for {col_type}")
            return None
        except ValueError as e:
            LOGGER.debug(f"Failed to convert python type: {e}")
            return None

    def _get_generic_type(self, col_type: TypeEngine) -> DataType | None:
        try:
            col_type = col_type.as_generic()
            return _sql_type_to_data_type(str(col_type))
        except NotImplementedError:
            LOGGER.debug("Generic type not available")
            return None
        except ValueError as e:
            LOGGER.debug(f"Failed to convert python type: {e}")
            return None

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
