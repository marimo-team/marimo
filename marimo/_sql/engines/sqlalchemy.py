# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import functools
import re
from contextlib import contextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    ParamSpec,
    TypeVar,
)

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
from marimo._sql.engines.types import InferenceConfig, SQLConnection
from marimo._sql.utils import (
    CHEAP_DISCOVERY_DATABASES,
    convert_to_output,
    sql_type_to_data_type,
)
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    import pandas as pd
    import polars as pl
    from sqlalchemy import Engine, Inspector
    from sqlalchemy.engine.cursor import CursorResult
    from sqlalchemy.engine.interfaces import ReflectedColumn, ReflectedIndex
    from sqlalchemy.sql.type_api import TypeEngine

# Quote if the identifier contains anything other than letters, digits, underscores, or dollar signs.
_SNOWFLAKE_NEEDS_QUOTING_RE = re.compile(r"[^A-Za-z0-9_$]")


# ------------------------------------------------------------------ #
#  Decorators                                                         #
# ------------------------------------------------------------------ #


T = TypeVar("T")
P = ParamSpec("P")
F = TypeVar("F")


def safe_execute(
    *,
    fallback: F,
    message: str = "Operation failed",
    log_level: Literal["debug", "info", "warning", "error"] = "warning",
    silent_exceptions: tuple[type[BaseException], ...] = (),
) -> Callable[[Callable[P, T]], Callable[P, T | F]]:
    """Catch exceptions, log them, and return a fallback value.

    Args:
        fallback: Value returned when the wrapped function raises.
        message: Message written to the logger on failure.
        log_level: Logger level – must be one of
            ``'debug'``, ``'info'``, ``'warning'``, or ``'error'``.
        silent_exceptions: Exception types that should return *fallback*
            without any logging.  Useful for expected control-flow
            exceptions like ``NotImplementedError``.
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T | F]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | F:
            try:
                return func(*args, **kwargs)
            except silent_exceptions:
                return fallback
            except Exception:
                getattr(LOGGER, log_level)(message, exc_info=True)
                return fallback

        return wrapper

    return decorator


# ------------------------------------------------------------------ #
#  SQLAlchemyEngine                                                   #
# ------------------------------------------------------------------ #


class SQLAlchemyEngine(SQLConnection["Engine"]):
    """SQLAlchemy engine."""

    def __init__(
        self, connection: Engine, engine_name: VariableName | None = None
    ) -> None:
        super().__init__(connection, engine_name)
        self.inspector: Inspector | None = None

        try:
            # May not exist in older versions of SQLAlchemy
            from sqlalchemy import inspect

            self.inspector = inspect(self._connection)
        except Exception:
            LOGGER.warning("Failed to create inspector", exc_info=True)
            self.inspector = None

        self.default_database = self.get_default_database()
        self.default_schema = self.get_default_schema()

    def _quote_identifier(self, identifier: str) -> str:
        """Quote an identifier based on the SQL dialect's quoting rules."""
        dialect_quoting: dict[str, tuple[re.Pattern[str], str, str]] = {
            "snowflake": (_SNOWFLAKE_NEEDS_QUOTING_RE, '"', '"'),
            "starrocks": (_SNOWFLAKE_NEEDS_QUOTING_RE, "`", "`"),
        }

        if self.dialect not in dialect_quoting:
            return identifier

        pattern, open_quote, close_quote = dialect_quoting[self.dialect]
        if pattern.search(identifier) or identifier != identifier.lower():
            escaped = identifier.replace(
                close_quote, close_quote + close_quote
            )
            return f"{open_quote}{escaped}{close_quote}"
        return identifier

    @contextmanager
    def _get_inspector(self, database: str) -> Iterator[Inspector | None]:
        """Yield an appropriate SQLAlchemy Inspector for the given database.

        For dialects that require a USE DATABASE command (e.g. Snowflake),
        this opens a connection, executes the command, and yields an
        inspector bound to that connection.

        For all other dialects, it yields ``self.inspector`` (which may
        be ``None``).

        Usage::

            with self._get_inspector(database) as inspector:
                if inspector is None:
                    return []
                return inspector.get_schema_names()
        """

        from sqlalchemy import inspect, text

        _use_database_dialect_command: dict[str, str] = {
            "snowflake": f"USE DATABASE {self._quote_identifier(database)}",
            "starrocks": f"SET CATALOG {self._quote_identifier(database)}",
        }
        dialect_command = _use_database_dialect_command.get(self.dialect)

        if dialect_command is not None:
            with self._connection.connect() as connection:
                connection.execute(text(dialect_command))
                yield inspect(connection)
        else:
            yield self.inspector

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

            def convert_to_polars() -> pl.DataFrame:
                import polars as pl

                return pl.DataFrame(rows)

            def convert_to_pandas() -> pd.DataFrame:
                import pandas as pd

                return pd.DataFrame(rows)

            return convert_to_output(
                sql_output_format=sql_output_format,
                to_polars=convert_to_polars,
                to_pandas=convert_to_pandas,
            )

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.sqlalchemy.imported():
            return False

        from sqlalchemy.engine import Engine

        return isinstance(var, Engine)

    @property
    def inference_config(self) -> InferenceConfig:
        return InferenceConfig(
            auto_discover_schemas="auto",
            auto_discover_tables="auto",
            auto_discover_columns=False,
        )

    def get_default_database(self) -> str | None:
        """Get the current database name.

        Returns:
            - The database name from the connection URL if available
            - The database name queried from the database if URL doesn't contain it
            - An empty string if the connection is detached but valid
            - None if the connection is invalid
        """

        from sqlalchemy import text

        try:
            if self._connection.url.database is not None and isinstance(
                self._connection.url.database, str
            ):
                return str(self._connection.url.database)
        except Exception:
            LOGGER.warning("Connection URL is invalid", exc_info=True)
            return None

        database_name: str | None = None
        dialect_queries = {
            "postgresql": "SELECT current_database()",
            "mssql": "SELECT DB_NAME()",
            "timeplus": "SELECT current_database()",
            "starrocks": "SELECT CATALOG()",
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
            schemas_found = self.get_schemas(
                database=None,
                include_tables=False,
                include_table_details=False,
            )
            if not schemas_found:
                return None

        return database_name or ""

    @safe_execute(
        fallback=None,
        message="Failed to get default schema name",
        log_level="warning",
    )
    def get_default_schema(self) -> str | None:
        """Get the default schema name"""
        if self.inspector is None:
            return None

        default_schema_name = self.inspector.default_schema_name
        # https://github.com/marimo-team/marimo/issues/6436.
        # Upstream bug where default schema name is not a string.
        if default_schema_name is None or not isinstance(
            default_schema_name, str
        ):
            return None
        return str(default_schema_name)

    # -------------------------------------------------------------- #
    #  Databases resolution                                           #
    # -------------------------------------------------------------- #

    # Get database names for SNOWFLAKE
    def _get_snowflake_database_names(self) -> list[str]:
        """Get database names for Snowflake via 'SHOW DATABASES'.

        If the default database exists in the results, return only that.
        Otherwise, return all discovered databases.

        Unquoted identifiers are normalized to lowercase for consistency.
        Identifiers that need quoting are preserved as-is.
        """
        from sqlalchemy import text

        with self._connection.connect() as connection:
            result = connection.execute(text("SHOW DATABASES"))
            columns = list(result.keys())

            try:
                name_col_index = columns.index("name")
            except ValueError as err:
                raise RuntimeError(
                    "Unexpected SHOW DATABASES result: "
                    f"'name' column not found in {columns}"
                ) from err

            database_names: list[str] = []
            for row in result.fetchall():
                raw_name = str(row[name_col_index])
                if (
                    _SNOWFLAKE_NEEDS_QUOTING_RE.search(raw_name)
                    or raw_name != raw_name.upper()
                ):
                    database_names.append(raw_name)
                else:
                    database_names.append(raw_name.lower())

        if self.default_database:
            default_lower = self.default_database.lower()
            for db in database_names:
                if db.lower() == default_lower:
                    return [db]

        return database_names

    def _get_starrocks_database_names(self) -> list[str]:
        """Get catalog names for StarRocks via 'SHOW CATALOGS'.

        StarRocks uses a three-level hierarchy (Catalog → Database → Table)
        which maps to marimo's (Database → Schema → Table).
        """
        from sqlalchemy import text

        with self._connection.connect() as connection:
            result = connection.execute(text("SHOW CATALOGS"))
            return [str(row[0]) for row in result.fetchall()]

    @safe_execute(
        fallback=[],
        message="Failed to get database names",
        log_level="warning",
    )
    def _get_database_names(self) -> list[str]:
        """Get database names using dialect-specific queries.

        Returns a single-element list with the default database when
        the dialect has no dedicated discovery mechanism.
        """
        dialect = self.dialect.lower()
        if dialect == "snowflake":
            return self._get_snowflake_database_names()
        if dialect == "starrocks":
            return self._get_starrocks_database_names()

        return [self.default_database] if self.default_database else []

    def get_databases(
        self,
        *,
        include_schemas: bool | Literal["auto"],
        include_tables: bool | Literal["auto"],
        include_table_details: bool | Literal["auto"],
    ) -> list[Database]:
        """Get all databases from the engine.

        Args:
            include_schemas: Include schema information per database.
            include_tables: Include table information within each schema.
            include_table_details: Include columns, PKs, and indexes
                for each table.

        Returns:
            List of Database objects representing the database structure.

        Note:
            This operation can be performance-intensive when fetching
            full metadata.
        """
        should_include_schemas = self._resolve_should_auto_discover(
            include_schemas
        )
        should_include_tables = self._resolve_should_auto_discover(
            include_tables
        )
        should_include_details = self._resolve_should_auto_discover(
            include_table_details
        )

        databases: list[Database] = []

        for database_name in self._get_database_names():
            schemas = (
                self.get_schemas(
                    database=database_name,
                    include_tables=should_include_tables,
                    include_table_details=should_include_details,
                )
                if should_include_schemas
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

    # -------------------------------------------------------------- #
    #  Schemas resolution                                            #
    # -------------------------------------------------------------- #

    @safe_execute(
        fallback=[], message="Failed to get schema names", log_level="warning"
    )
    def _get_schema_names(self, database: str) -> list[str]:

        with self._get_inspector(database) as inspector:
            if inspector is None:
                return []
            return inspector.get_schema_names()

    def get_schemas(
        self,
        *,
        database: str | None,
        include_tables: bool,
        include_table_details: bool,
    ) -> list[Schema]:
        """Get all schemas and optionally their tables. Keys are schema names."""

        if database is None:
            schema_names: list[str] = []
        else:
            schema_names = self._get_schema_names(database)

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
        if dialect == "starrocks":
            return ["information_schema", "sys", "_statistics_"]
        return ["information_schema"]

    # -------------------------------------------------------------- #
    #  Tables resolution                                             #
    # -------------------------------------------------------------- #

    @safe_execute(
        fallback=([], []),
        message="Failed to get tables in schema",
        log_level="warning",
    )
    def _get_table_names(
        self, schema: str, database: str
    ) -> tuple[list[str], list[str]]:

        with self._get_inspector(database) as inspector:
            if inspector is None:
                return [], []
            return inspector.get_table_names(
                schema=schema
            ), inspector.get_view_names(schema=schema)

    def get_tables_in_schema(
        self, *, schema: str, database: str, include_table_details: bool
    ) -> list[DataTable]:
        """Return all tables in a schema."""

        table_names, view_names = self._get_table_names(
            schema=schema, database=database
        )

        tables: list[tuple[DataTableType, str]] = []
        for name in table_names:
            tables.append(("table", name))
        for name in view_names:
            tables.append(("view", name))

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

    # -------------------------------------------------------------- #
    #  Table Details resolution                                      #
    # -------------------------------------------------------------- #

    @safe_execute(
        fallback=None,
        message="Failed to get table details",
        log_level="warning",
    )
    def _get_columns(
        self, table_name: str, schema: str, database: str
    ) -> list[ReflectedColumn] | None:

        with self._get_inspector(database) as inspector:
            if inspector is None:
                return None
            return inspector.get_columns(table_name, schema=schema)

    @safe_execute(fallback=[], message="Failed to get primary keys")
    def _fetch_primary_keys(
        self, table_name: str, schema: str, database: str
    ) -> list[str]:

        with self._get_inspector(database) as inspector:
            if inspector is None:
                return []
            return inspector.get_pk_constraint(table_name, schema=schema).get(
                "constrained_columns", []
            )

    @safe_execute(fallback=[], message="Failed to get indexes")
    def _fetch_indexes(
        self, table_name: str, schema: str, database: str
    ) -> list[str]:

        with self._get_inspector(database) as inspector:
            if inspector is None:
                return []
            indexes = inspector.get_indexes(table_name, schema=schema)
            return self._extract_index_columns(indexes)

    @staticmethod
    def _extract_index_columns(indexes: list[ReflectedIndex]) -> list[str]:
        """Extract and deduplicate column names from a list of index definitions."""
        index_columns: list[str] = []
        seen: set[str] = set()
        for index in indexes:
            if index_cols := index.get("column_names"):
                for col in index_cols:
                    if col is not None and col not in seen:
                        seen.add(col)
                        index_columns.append(col)
        return index_columns

    def get_table_details(
        self, *, table_name: str, schema_name: str, database_name: str
    ) -> DataTable | None:
        """Get a single table from the engine."""

        columns = self._get_columns(
            table_name, schema=schema_name, database=database_name
        )
        if columns is None:
            return None

        primary_keys = self._fetch_primary_keys(
            table_name, schema_name, database_name
        )
        index_list = self._fetch_indexes(
            table_name, schema_name, database_name
        )

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

    @safe_execute(
        fallback=None,
        message="Failed to get column type",
        log_level="warning",
        silent_exceptions=(NotImplementedError,),
    )
    def _get_python_type(
        self, engine_type: TypeEngine[Any]
    ) -> DataType | None:
        col_type = engine_type.python_type
        return sql_type_to_data_type(str(col_type))

    @safe_execute(
        fallback=None,
        message="Failed to get generic type",
        log_level="debug",
        silent_exceptions=(NotImplementedError,),
    )
    def _get_generic_type(
        self, engine_type: TypeEngine[Any]
    ) -> DataType | None:
        col_type = engine_type.as_generic()
        return sql_type_to_data_type(str(col_type))

    def _resolve_should_auto_discover(
        self,
        value: bool | Literal["auto"],
    ) -> bool:
        if value == "auto":
            return self._is_cheap_discovery()
        return value

    def _is_cheap_discovery(self) -> bool:
        return self.dialect.lower() in CHEAP_DISCOVERY_DATABASES

    @staticmethod
    def is_cursor_result(result: Any) -> bool:
        if not DependencyManager.sqlalchemy.has():
            return False

        from sqlalchemy.engine.cursor import CursorResult

        return isinstance(result, CursorResult)

    @staticmethod
    def get_cursor_metadata(
        result: CursorResult[Any],
    ) -> dict[str, Any]:
        try:
            column_info = None
            if result.cursor is not None:
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
                sql_statement_type = "Query / Unknown"

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
            return {
                "result_type": str(type(result)),
                "error": "Failed to convert cursor result to df",
            }
