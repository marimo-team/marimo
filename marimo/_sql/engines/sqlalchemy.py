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
    SQLConnection,
    register_engine,
)
from marimo._sql.utils import raise_df_import_error, sql_type_to_data_type
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from sqlalchemy import Engine, Inspector
    from sqlalchemy.engine.cursor import CursorResult
    from sqlalchemy.sql.type_api import TypeEngine


@register_engine
class SQLAlchemyEngine(SQLConnection["Engine"]):
    """SQLAlchemy engine."""

    def __init__(
        self, connection: Engine, engine_name: Optional[VariableName] = None
    ) -> None:
        super().__init__(connection, engine_name)
        self.inspector: Optional[Inspector] = None

        try:
            # May not exist in older versions of SQLAlchemy
            from sqlalchemy import inspect

            self.inspector = inspect(self._connection)
        except Exception:
            LOGGER.warning("Failed to create inspector", exc_info=True)
            self.inspector = None

        self.default_database = self.get_default_database()
        self.default_schema = self.get_default_schema()

    @property
    def source(self) -> str:
        return "sqlalchemy"

    @property
    def dialect(self) -> str:
        return str(self._connection.dialect.name)

    def execute(self, query: str) -> Any:
        sql_output_format = self.sql_output_format()

        from sqlalchemy import text

        with self._connection.connect() as connection:
            result = connection.execute(text(query))
            if sql_output_format == "native":
                return result

            rows = result.fetchall() if result.returns_rows else None

            try:
                connection.commit()
            except Exception:
                LOGGER.info("Unable to commit transaction", exc_info=True)

            if rows is None:
                return None

            if sql_output_format == "polars":
                import polars as pl

                return pl.DataFrame(rows)  # type: ignore
            if sql_output_format == "lazy-polars":
                import polars as pl

                return pl.DataFrame(rows).lazy()  # type: ignore
            if sql_output_format == "pandas":
                import pandas as pd

                return pd.DataFrame(rows)

            # Auto

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

            raise_df_import_error("polars[pyarrow]")

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
            if self._connection.url.database is not None:
                return self._connection.url.database
        except Exception:
            LOGGER.warning("Connection URL is invalid", exc_info=True)
            return None

        database_name: Optional[str] = None
        dialect_queries = {
            "postgresql": "SELECT current_database()",
            "mssql": "SELECT DB_NAME()",
            "timeplus": "SELECT current_database()",
        }

        # Try to get the database name by querying the database directly
        if query := dialect_queries.get(self.dialect):
            try:
                with self._connection.connect() as connection:
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
            tables: list[DataTable] = []
            meta_schemas = self._get_meta_schemas()
            if schema.lower() not in meta_schemas and include_tables:
                tables = self.get_tables_in_schema(
                    schema=schema,
                    database=database if database is not None else "",
                    include_table_details=include_table_details,
                )
            schemas.append(Schema(name=schema, tables=tables))

        return schemas

    def _get_meta_schemas(self) -> list[str]:
        dialect = self.dialect.lower()
        if dialect == "postgresql":
            return ["information_schema", "pg_catalog"]
        return ["information_schema"]

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

    @staticmethod
    def is_cursor_result(result: Any) -> bool:
        if not DependencyManager.sqlalchemy.has():
            return False

        from sqlalchemy.engine.cursor import CursorResult

        return isinstance(result, CursorResult)

    @staticmethod
    def get_cursor_metadata(
        result: CursorResult[Any],
    ) -> Optional[dict[str, Any]]:
        try:
            description = result.cursor.description
            column_info = {
                "column_names": [col[0] for col in description],
                "type_code": [col[1] for col in description],
                "display_size": [col[2] for col in description],
                "internal_size": [col[3] for col in description],
                "precision": [col[4] for col in description],
                "scale": [col[5] for col in description],
                "null_ok": [col[6] for col in description],
            }

            if result.context.isddl:
                sql_statement_type = "DDL"
            elif result.context.is_crud:
                sql_statement_type = "DML"
            else:
                sql_statement_type = "Query"

            data = {
                "result_type": str(type(result)),
                "column_info": column_info,
                "sqlalchemy_rowcount": result.rowcount,
                "sql_statement_type": sql_statement_type,
                "cache_status": str(result.context.cache_hit.name),
            }

            return data
        except Exception:
            LOGGER.warning(
                "Failed to convert cursor result to df", exc_info=True
            )
            return None
