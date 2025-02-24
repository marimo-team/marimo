# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, cast

from marimo import _loggers
from marimo._data.get_datasets import get_databases_from_duckdb
from marimo._data.models import (
    Database,
    DataTable,
    DataTableColumn,
    DataTableType,
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

# Internal engine name for DuckDB, we need to ensure this is unique
INTERNAL_DUCKDB_ENGINE = cast(VariableName, "__marimo_duckdb")


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
            raise_df_import_error("polars")

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.duckdb.imported():
            return False

        import duckdb

        return isinstance(var, duckdb.DuckDBPyConnection)

    def get_databases(self) -> list[Database]:
        """Fetch all databases from the engine. At the moment, will fetch everything."""
        return get_databases_from_duckdb(self._connection, self._engine_name)


class SQLAlchemyEngine(SQLEngine):
    """SQLAlchemy engine."""

    def __init__(
        self, engine: Engine, engine_name: Optional[VariableName] = None
    ) -> None:
        from sqlalchemy import Inspector, inspect

        self._engine = engine
        self._engine_name = engine_name
        self.inspector: Optional[Inspector] = None
        try:
            self.inspector = inspect(self._engine)
        except Exception:
            LOGGER.warning("Failed to create inspector", exc_info=True)
            self.inspector = None

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
            rows = result.fetchall() if result.returns_rows else None

            try:
                connection.commit()
            except Exception:
                LOGGER.info("Unable to commit transaction", exc_info=True)

            if rows is None:
                return None

            if DependencyManager.polars.has():
                import polars as pl

                return pl.DataFrame(rows)  # type: ignore
            else:
                import pandas as pd

                return pd.DataFrame(rows)

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

    def get_database_name(self) -> Optional[str]:
        """Get the current database name."""

        from sqlalchemy import text

        if self._engine.url.database is not None:
            return self._engine.url.database

        # If there is no database name, the engine may connect to a default database.
        # which may not show up in the url
        try:
            query: str
            if self.dialect in ("postgresql"):
                query = "SELECT current_database()"
            elif self.dialect in ("mssql"):
                query = "SELECT DB_NAME()"
            if query is None:
                return None

            with self._engine.connect() as connection:
                rows = connection.execute(text(query)).fetchone()
                if rows is None or rows[0] is None:
                    return None
                return str(rows[0])
        except Exception:
            LOGGER.warning(
                "Failed to get current database name", exc_info=True
            )
            return None

    def get_databases(
        self,
        *,
        include_schemas: bool = False,
        include_tables: bool = False,
        include_table_details: bool = False,
    ) -> list[Database]:
        """Get all databases from the engine.

        Args:
            include_schemas: Whether to include schema information. If False, databases will have empty schemas.
            include_tables: Whether to include table information within schemas. If False, schemas will have empty tables.
            include_table_details: Whether to include each table's detailed information. If False, tables will have empty columns, PK, indexes.

        Returns:
            List of Database objects representing the database structure.

        Note: This operation can be performance intensive when fetching full metadata.
        """
        databases: list[Database] = []
        database_name = self.get_database_name()

        # If database_name is None, the connection might be detached or invalid.
        # We check for existing schemas to verify the connection's validity.
        # If valid, set database_name to an empty string to indicate it's detached.
        if database_name is None:
            schemas_found = self._get_schemas(
                include_tables=False, include_table_details=False
            )
            if not schemas_found:
                return []
            database_name = ""

        schemas = (
            self._get_schemas(
                include_tables=include_tables,
                include_table_details=include_table_details,
            )
            if include_schemas
            else []
        )
        databases.append(
            Database(
                name=database_name,
                dialect=self.dialect,
                schemas=schemas,
                engine=self._engine_name,
            )
        )
        return databases

    def _get_schemas(
        self,
        *,
        include_tables: bool,
        include_table_details: bool,
    ) -> list[Schema]:
        """Get all schemas and optionally their tables. Keys are schema names."""

        if self.inspector is None:
            return []
        try:
            schema_names = self.inspector.get_schema_names()
        except Exception:
            LOGGER.warning("Failed to get schema names", exc_info=True)
            return []
        schemas: list[Schema] = []

        for schema in schema_names:
            schemas.append(
                Schema(
                    name=schema,
                    tables=self._get_tables_in_schema(
                        schema=schema,
                        include_table_details=include_table_details,
                    )
                    if include_tables
                    else [],
                )
            )

        return schemas

    def _get_tables_in_schema(
        self, *, schema: str, include_table_details: bool
    ) -> list[DataTable]:
        """Return all tables in a schema."""

        if self.inspector is None:
            return []
        try:
            table_names = self.inspector.get_table_names(schema=schema)
            view_names = self.inspector.get_view_names(schema=schema)
        except Exception:
            LOGGER.warning("Failed to get tables in schema", exc_info=True)
            return []
        tables: list[tuple[DataTableType, str]] = [
            ("table", name) for name in table_names
        ] + [("view", name) for name in view_names]

        if not include_table_details:
            return [
                DataTable(
                    source_type="connection",
                    source=self.dialect,
                    name=name,
                    num_rows=None,
                    num_columns=None,
                    variable_name=None,
                    engine=self._engine_name,
                    type=table_type,
                    columns=[],
                    primary_keys=[],
                    indexes=[],
                )
                for table_type, name in tables
            ]

        data_tables: list[DataTable] = []
        for t_type, t_name in tables:
            table = self.get_table_details(t_name, schema)
            if table is not None:
                table.type = t_type
                data_tables.append(table)

        return data_tables

    def get_table_details(
        self, table_name: str, schema_name: str
    ) -> Optional[DataTable]:
        """Get a single table from the engine."""

        if self.inspector is None:
            return None
        try:
            columns = self.inspector.get_columns(
                table_name, schema=schema_name
            )
        except Exception:
            LOGGER.warning(
                f"Failed to get table {table_name} in schema {schema_name}",
                exc_info=True,
            )
            return None

        primary_keys: list[str] = []
        index_list: list[str] = []

        try:
            primary_keys = self.inspector.get_pk_constraint(
                table_name, schema=schema_name
            )["constrained_columns"]
        except Exception:
            pass

        # TODO: Handle multi column PK and indexes
        try:
            indexes = self.inspector.get_indexes(
                table_name, schema=schema_name
            )
            for index in indexes:
                if index_cols := index["column_names"]:
                    index_list.extend(
                        col for col in index_cols if col is not None
                    )
        except Exception:
            LOGGER.warning("Failed to get indexes", exc_info=True)
            pass

        cols: list[DataTableColumn] = []
        for col in columns:
            engine_type = col["type"]
            col_type: DataType = (
                self._get_python_type(engine_type)
                or self._get_generic_type(engine_type)
                or "string"
            )

            cols.append(
                DataTableColumn(
                    name=col["name"],
                    type=col_type,
                    external_type=str(engine_type),
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

    def _get_python_type(
        self, engine_type: TypeEngine[Any]
    ) -> DataType | None:
        try:
            col_type = engine_type.python_type
            return _sql_type_to_data_type(str(col_type))
        except NotImplementedError:
            return None
        except Exception:
            LOGGER.debug("Failed to get python type", exc_info=True)
            return None

    def _get_generic_type(
        self, engine_type: TypeEngine[Any]
    ) -> DataType | None:
        try:
            col_type = engine_type.as_generic()
            return _sql_type_to_data_type(str(col_type))
        except NotImplementedError:
            return None
        except Exception:
            LOGGER.debug("Failed to get generic type", exc_info=True)
            return None


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
