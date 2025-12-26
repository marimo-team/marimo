# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Optional, Union

from marimo import _loggers
from marimo._data.models import (
    Database,
    DataTable,
    DataTableColumn,
    DataType,
    Schema,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.types import InferenceConfig, SQLConnection
from marimo._sql.utils import CHEAP_DISCOVERY_DATABASES, convert_to_output
from marimo._types.ids import VariableName

if TYPE_CHECKING:
    from ibis.backends.sql import SQLBackend  # type: ignore
    from ibis.expr import datatypes as dt  # type: ignore

LOGGER = _loggers.marimo_logger()


class IbisToMarimoConversionError(Exception):
    """Raise for unhandled type during Ibis to Marimo conversion"""


class IbisEngine(SQLConnection["SQLBackend"]):
    """Ibis engine."""

    def __init__(
        self,
        connection: SQLBackend,
        engine_name: Optional[VariableName] = None,
    ) -> None:
        super().__init__(connection, engine_name)

        self.default_database = self.get_default_database()
        self.default_schema = self.get_default_schema()

    @property
    def source(self) -> str:
        return "ibis"

    @property
    def dialect(self) -> str:
        dialect_registry = self._connection.dialect.classes
        # reverse lookup
        for dialect_name, dialect_class in dialect_registry.items():
            if self._connection.dialect == dialect_class:
                assert isinstance(dialect_name, str)
                return dialect_name

        return str(self._connection.dialect)

    def execute(self, query: str) -> Any:
        query_expr = self._connection.sql(query)

        sql_output_format = self.sql_output_format()

        return convert_to_output(
            sql_output_format=sql_output_format,
            to_polars=lambda: query_expr.to_polars(),
            to_pandas=lambda: query_expr.to_pandas(),
            to_native=lambda: query_expr,
        )

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.ibis.imported():
            return False

        from ibis import BaseBackend  # type: ignore
        from ibis.backends.sql import SQLBackend  # type: ignore

        if isinstance(var, BaseBackend) and not isinstance(var, SQLBackend):
            LOGGER.debug(
                f"Ibis backend found, but it's not an SQLBackend subclass. Variable name: {var}"
            )

        return isinstance(var, SQLBackend)

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
        database_name = None
        try:
            database_name = str(self._connection.current_catalog)
        except AttributeError:
            LOGGER.debug("Backend doesn't support current_catalog")
        except Exception:
            LOGGER.debug("Failed to get default database", exc_info=True)

        if database_name is None:
            try:
                database_name = str(self._connection.name)
            except AttributeError:
                LOGGER.debug("Backend doesn't have a connection name")
            except Exception:
                LOGGER.debug("Failed to get default database", exc_info=True)

        return database_name

    def get_default_schema(self) -> Optional[str]:
        """Get the default schema name"""
        schema_name = None
        try:
            schema_name = str(self._connection.current_database)
        except AttributeError:
            LOGGER.debug("Backend doesn't support current_database")
        except Exception:
            LOGGER.debug("Failed to get default schema", exc_info=True)

        return schema_name

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
        # Note: Delegation to DuckDBEngine was attempted but get_databases_from_duckdb()
        # has a bug where it doesn't properly handle empty databases. Reverting to
        # working inline SQL approach.

        # For other Ibis backends, use original logic
        databases = []

        try:
            if hasattr(self._connection, "list_catalogs"):
                database_names = self._connection.list_catalogs()
            else:
                database_names = [self.default_database]
        except Exception:
            LOGGER.debug("Failed to get databases", exc_info=True)
            return []

        for database_name in database_names:
            database_name_str = str(database_name)
            if self._resolve_should_auto_discover(include_schemas):
                schemas = self._get_schemas(
                    database=database_name_str,
                    include_tables=self._resolve_should_auto_discover(
                        include_tables
                    ),
                    include_table_details=self._resolve_should_auto_discover(
                        include_table_details
                    ),
                )
            else:
                schemas = []

            database: Database = Database(
                name=database_name_str,
                dialect=self.dialect,
                schemas=schemas,
                engine=self._engine_name,
            )

            databases.append(database)

        return databases

    def _get_schemas(
        self,
        *,
        database: Optional[str],
        include_tables: bool,
        include_table_details: bool,
    ) -> list[Schema]:
        """Get all schemas and optionally their tables. Keys are schema names."""
        meta_schemas = self._get_meta_schemas()

        schemas: list[Schema] = []

        try:
            schema_names = self._connection.list_databases(catalog=database)
        except (TypeError, AttributeError) as e:
            # Backend doesn't support catalog parameter or list_databases method
            LOGGER.debug(
                f"Backend doesn't support catalog-based database listing: {e}"
            )
            try:
                # Fallback: try without catalog parameter
                schema_names = self._connection.list_databases()
            except (TypeError, AttributeError):
                # Backend doesn't support list_databases at all
                LOGGER.debug(
                    "Backend doesn't support list_databases, using default schema"
                )
                schema_names = [self.default_schema or "main"]
        except NotImplementedError:
            LOGGER.info("Introspection is not supported for this database")
            return []
        except Exception:
            LOGGER.warning(
                "Failed to get schemas for this database", exc_info=True
            )
            return []

        for schema_name in schema_names:
            if schema_name and schema_name.lower() in meta_schemas:
                LOGGER.debug(
                    f"Meta schema found `{schema_name}`. Not displaying schema."
                )
                continue

            tables: list[DataTable] = []
            if include_tables:
                tables = self.get_tables_in_schema(
                    schema=schema_name,
                    database=database if database is not None else "",
                    include_table_details=include_table_details,
                )

                # ignore schemas with 0 tables
                if len(tables) == 0:
                    LOGGER.debug(
                        f"No table found for schema `{schema_name}`. Not displaying schema."
                    )

            schema = Schema(name=schema_name, tables=tables)
            schemas.append(schema)

        return schemas

    def _get_meta_schemas(self) -> list[str]:
        """List of schemas for internal tables we want to ignore."""
        # TODO find a way to support meta schemas from all Ibis backends
        return ["information_schema", "pg_catalog"]

    def get_tables_in_schema(
        self, *, schema: str, database: str, include_table_details: bool
    ) -> list[DataTable]:
        """Return all tables in a schema."""
        if self._connection is None:
            return []

        try:
            # Try tuple format first (works for DuckDB and most backends)
            try:
                table_names = self._connection.list_tables(
                    database=(database, schema)
                )
            except (TypeError, Exception):
                # Fallback: try just schema (works for SQLite and other simple backends)
                LOGGER.debug(
                    f"Tuple database parameter failed, trying schema only for {database}.{schema}"
                )
                table_names = self._connection.list_tables(database=schema)

            # For DuckDB: filter out temp-only tables when NOT in temp catalog
            if self._is_duckdb_backend() and database.lower() != "temp":
                table_names = self._filter_out_temp_only_tables(
                    table_names, schema, database
                )

        except Exception:
            LOGGER.warning(
                f"Failed to get tables from database {database}", exc_info=True
            )
            return []

        # NOTE ibis can't distinguish tables and views
        tables: list[DataTable] = []
        for table_name in table_names:
            if include_table_details:
                table = self.get_table_details(
                    table_name=table_name,
                    schema_name=schema,
                    database_name=database,
                )
                if table is None:
                    continue
            else:
                table = DataTable(
                    source_type="connection",
                    source=self.source,
                    name=table_name,
                    num_rows=None,
                    num_columns=None,
                    variable_name=None,
                    engine=self._engine_name,
                    type="table",
                    columns=[],
                    primary_keys=None,
                    indexes=None,
                )
            tables.append(table)

        return tables

    def _is_duckdb_backend(self) -> bool:
        """Check if we're using DuckDB backend."""
        return (
            hasattr(self._connection, "name")
            and self._connection.name == "duckdb"
        )

    def _filter_out_temp_only_tables(
        self, table_names: list[str], schema: str, current_database: str
    ) -> list[str]:
        """Filter out tables that exist ONLY in temp catalog.

        For DuckDB: When querying a non-temp catalog, DuckDB's list_tables includes temp tables.
        We need to filter these out by checking which tables actually exist in the target catalog.

        ref: https://github.com/ibis-project/ibis/blob/324b882057ac3cf2bfec098679719c1c1936a084/ibis/backends/duckdb/__init__.py#L866
        """
        try:
            # Query the target catalog directly to get tables that actually exist there
            target_catalog_sql = f"""
                SELECT DISTINCT table_name
                FROM information_schema.tables
                WHERE table_catalog = '{current_database}'
                AND table_schema = '{schema}'
            """
            result = self._connection.con.execute(
                target_catalog_sql
            ).fetchall()
            target_catalog_tables = {row[0] for row in result}

            # Keep only tables that exist in the target catalog
            filtered = [
                table
                for table in table_names
                if table in target_catalog_tables
            ]
            return filtered

        except Exception as e:
            LOGGER.debug(f"Failed to filter temp tables: {e}")
            # If filtering fails, just dedupe and return
            return list(set(table_names))

    def get_table_details(
        self, *, table_name: str, schema_name: str, database_name: str
    ) -> Optional[DataTable]:
        """Get a single table from the engine."""
        if self._connection is None:
            return None

        try:
            table = self._connection.table(
                table_name, database=(database_name, schema_name)
            )
            table_schema = table.schema()
        except Exception:
            LOGGER.warning(
                f"Failed to get details for {table_name} in database {database_name}",
                exc_info=True,
            )
            return None

        cols: list[DataTableColumn] = []
        for col_name, ibis_dtype in table_schema.fields.items():
            try:
                col_type: DataType = self._ibis_to_marimo_dtype(ibis_dtype)
            except IbisToMarimoConversionError:
                col_type = "string"
                LOGGER.warning(
                    f"Failed to convert column `{col_name}` with ibis dtype `{ibis_dtype}` to marimo dtype."
                    " Defaulting to `string`."
                )

            # type and external_type will always match; ibis is unaware of physical type
            cols.append(
                DataTableColumn(
                    name=col_name,
                    type=col_type,
                    external_type=str(ibis_dtype),
                    sample_values=[],
                )
            )

        # num_rows is not in metadata and would require a count or approx_count
        # ibis is unaware of primary keys and indices
        return DataTable(
            source_type="connection",
            source=self.source,
            name=table_name,
            num_rows=None,
            num_columns=len(table_schema.fields),
            variable_name=None,
            engine=self._engine_name,
            columns=cols,
            primary_keys=None,
            indexes=None,
        )

    @staticmethod
    def _ibis_to_marimo_dtype(ibis_dtype: dt.DataType) -> DataType:
        """Map the Ibis typing system to marimo SQL types.

        Ibis datatypes ref: https://ibis-project.org/reference/datatypes
        """
        if ibis_dtype.is_integer():
            return "integer"
        # numeric is a superset of integer, so we evaluate after is_integer
        elif ibis_dtype.is_numeric():
            return "number"
        elif ibis_dtype.is_date():
            return "date"
        elif ibis_dtype.is_timestamp():
            return "datetime"
        elif ibis_dtype.is_time():
            return "time"
        elif ibis_dtype.is_temporal():
            return "datetime"
        elif ibis_dtype.is_interval():
            return "string"
        elif ibis_dtype.is_boolean():
            return "boolean"
        elif ibis_dtype.is_string():
            return "string"
        elif ibis_dtype.is_binary():
            return "string"
        elif ibis_dtype.is_array():
            return "unknown"
        elif ibis_dtype.is_map():
            return "unknown"
        elif ibis_dtype.is_struct():
            return "unknown"
        elif ibis_dtype.is_json():
            return "unknown"
        elif ibis_dtype.is_uuid():
            return "string"
        elif ibis_dtype.is_macaddr():
            return "string"
        elif ibis_dtype.is_inet():
            return "string"
        elif ibis_dtype.is_linestring():
            return "string"
        elif ibis_dtype.is_multilinestring():
            return "string"
        else:
            raise IbisToMarimoConversionError

    def _resolve_should_auto_discover(
        self,
        value: Union[bool, Literal["auto"]],
    ) -> bool:
        if value == "auto":
            return self._is_cheap_discovery()
        return value

    def _is_cheap_discovery(self) -> bool:
        return self.dialect.lower() in CHEAP_DISCOVERY_DATABASES
