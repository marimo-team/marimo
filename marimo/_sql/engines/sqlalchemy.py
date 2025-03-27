# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Optional, Union

from marimo import _loggers
from marimo._data.models import (
    Database,
    DataTable,
    DataTableColumn,
    DataTableType,
    DataType,
    Schema,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.types import (
    InferenceConfig,
    SQLEngine,
    register_engine,
)
from marimo._sql.utils import raise_df_import_error, sql_type_to_data_type
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.sql.type_api import TypeEngine


@register_engine
class SQLAlchemyEngine(SQLEngine):
    """SQLAlchemy engine."""

    def __init__(
        self, connection: Engine, engine_name: Optional[VariableName] = None
    ) -> None:
        from sqlalchemy import Inspector, inspect

        self._engine = connection
        self._engine_name = engine_name
        self.inspector: Optional[Inspector] = None

        try:
            self.inspector = inspect(self._engine)
        except Exception:
            LOGGER.warning("Failed to create inspector", exc_info=True)
            self.inspector = None

        self.default_database = self.get_default_database()
        self.default_schema = self.get_default_schema()

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
            raise_df_import_error("polars[pyarrow]")

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

                try:
                    return pl.DataFrame(rows)  # type: ignore
                except (
                    pl.exceptions.PanicException,
                    pl.exceptions.ComputeError,
                ):
                    LOGGER.info(
                        "Failed to convert to polars, falling back to pandas"
                    )

            if DependencyManager.pandas.has():
                import pandas as pd

                try:
                    return pd.DataFrame(rows)
                except Exception as e:
                    LOGGER.warning("Failed to convert dataframe", exc_info=e)
                    return None

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.sqlalchemy.imported():
            return False

        from sqlalchemy.engine import Engine

        return isinstance(var, Engine)

    @property
    def inference_config(self) -> InferenceConfig:
        return InferenceConfig(
            auto_discover_schemas=True,
            auto_discover_tables="auto",
            auto_discover_columns=False,
        )

    def get_default_database(self) -> Optional[str]:
        """Get the current database name.

        Returns:
            - The database name from the connection URL if available
            - The database name queried from the database if URL doesn't contain it
            - An empty string if the connection is detached but valid
            - None if the connection is invalid
        """

        from sqlalchemy import text

        try:
            if self._engine.url.database is not None:
                return self._engine.url.database
        except Exception:
            LOGGER.warning("Connection URL is invalid", exc_info=True)
            return None

        database_name: Optional[str] = None
        dialect_queries = {
            "postgresql": "SELECT current_database()",
            "mssql": "SELECT DB_NAME()",
        }

        # Try to get the database name by querying the database directly
        if query := dialect_queries.get(self.dialect):
            try:
                with self._engine.connect() as connection:
                    rows = connection.execute(text(query)).fetchone()
                    if rows is not None and rows[0] is not None:
                        database_name = str(rows[0])
            except Exception:
                LOGGER.warning(
                    "Failed to get current database name", exc_info=True
                )

        # If database_name is None, the connection might be detached or invalid.
        # We check for existing schemas to verify the connection's validity.
        if database_name is None:
            schemas_found = self._get_schemas(
                database=None,
                include_tables=False,
                include_table_details=False,
            )
            if not schemas_found:
                return None

        return database_name or ""

    def get_default_schema(self) -> Optional[str]:
        """Get the default schema name"""
        if self.inspector is None:
            return None

        try:
            return self.inspector.default_schema_name
        except Exception:
            LOGGER.warning("Failed to get default schema name", exc_info=True)
            return None

    def get_databases(
        self,
        *,
        include_schemas: Union[bool, Literal["auto"]],
        include_tables: Union[bool, Literal["auto"]],
        include_table_details: Union[bool, Literal["auto"]],
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

        if self.default_database is None:
            return databases
        database_name = self.default_database

        schemas = (
            self._get_schemas(
                database=database_name,
                include_tables=self._resolve_should_auto_discover(
                    include_tables
                ),
                include_table_details=self._resolve_should_auto_discover(
                    include_table_details
                ),
            )
            if self._resolve_should_auto_discover(include_schemas)
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
        database: Optional[str],
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
                    tables=self.get_tables_in_schema(
                        schema=schema,
                        database=database if database is not None else "",
                        include_table_details=include_table_details,
                    )
                    if include_tables
                    else [],
                )
            )

        return schemas

    def get_tables_in_schema(
        self, *, schema: str, database: str, include_table_details: bool
    ) -> list[DataTable]:
        """Return all tables in a schema."""
        _ = database

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
            table = self.get_table_details(
                table_name=t_name, schema_name=schema, database_name=database
            )
            if table is not None:
                table.type = t_type
                data_tables.append(table)

        return data_tables

    def get_table_details(
        self, *, table_name: str, schema_name: str, database_name: str
    ) -> Optional[DataTable]:
        """Get a single table from the engine."""
        _ = database_name

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
            return sql_type_to_data_type(str(col_type))
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
            return sql_type_to_data_type(str(col_type))
        except NotImplementedError:
            return None
        except Exception:
            LOGGER.debug("Failed to get generic type", exc_info=True)
            return None

    def _resolve_should_auto_discover(
        self,
        value: Union[bool, Literal["auto"]],
    ) -> bool:
        if value == "auto":
            return self._is_cheap_discovery()
        return value

    def _is_cheap_discovery(self) -> bool:
        return self.dialect.lower() in ("sqlite", "mysql", "postgresql")
