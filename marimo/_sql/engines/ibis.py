from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Optional, Union

from ibis import BaseBackend
from ibis.backends.sql import SQLBackend

from marimo import _loggers
from marimo._data.models import (
    Database,
    DataTable,
    DataTableColumn,
    DataType,
    Schema,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._sql.engines.types import (
    InferenceConfig,
    SQLEngine,
    register_engine,
)
from marimo._sql.utils import raise_df_import_error
from marimo._types.ids import VariableName

if TYPE_CHECKING:
    from ibis.expr import datatypes as dt

LOGGER = _loggers.marimo_logger()


class IbisToMarimoConversionError(Exception):
    """Raise for unhandled type during Ibis to Marimo conversion"""


@register_engine
class IbisEngine(SQLEngine):
    """Ibis engine."""

    def __init__(
        self,
        connection: SQLBackend,
        engine_name: Optional[VariableName] = None,
    ) -> None:
        self._backend = connection
        self._engine_name = engine_name

        self.default_database = self.get_default_database()
        self.default_schema = self.get_default_schema()

    @property
    def source(self) -> str:
        # TODO should this be the backend name, the SQL dialect, or ibis?
        return "ibis"

    @property
    def dialect(self) -> str:
        dialect_registry = self._backend.dialect.classes
        # reverse lookup
        for dialect_name, dialect_class in dialect_registry.items():
            if self._backend.dialect == dialect_class:
                return dialect_name

        return str(self._backend.dialect)

    def execute(self, query: str) -> Any:
        query_expr = self._backend.sql(query)

        sql_output_format = self.sql_output_format()

        if sql_output_format == "native":
            return query_expr  # ibis.expr.types.Table; lazy

        if sql_output_format == "polars":
            return query_expr.to_polars()

        if sql_output_format == "lazy-polars":
            import polars as pl

            return pl.DataFrame(query_expr.to_polars()).lazy()  # type: ignore

        if sql_output_format == "pandas":
            return query_expr.to_pandas()

        # Auto
        if DependencyManager.polars.has():
            import polars as pl

            try:
                return query_expr.to_polars()
            except (
                pl.exceptions.PanicException,
                pl.exceptions.ComputeError,
            ):
                LOGGER.info(
                    "Failed to convert to polars, falling back to pandas"
                )

        if DependencyManager.pandas.has():
            try:
                return query_expr.to_pandas()
            except Exception as e:
                LOGGER.warning("Failed to convert dataframe", exc_info=e)
                return None

        raise_df_import_error("polars[pyarrow]")

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if isinstance(var, BaseBackend) and not isinstance(var, SQLBackend):
            LOGGER.debug(
                f"Ibis backend found, but it's not an SQLBackend subclass. {var}"
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
            database_name = self._backend.current_catalog
        except AttributeError:
            pass

        if database_name is None:
            try:
                database_name = self._backend.name
            except AttributeError:
                pass

        return database_name

    def get_default_schema(self) -> Optional[str]:
        """Get the default schema name"""
        try:
            schema_name = self._backend.current_database
        except AttributeError:
            schema_name = None

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
        if self.default_database is None:
            return []

        database_name = self.default_database
        if self._resolve_should_auto_discover(include_schemas):
            schemas = self._get_schemas(
                database=database_name,
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
            name=database_name,
            dialect=self.dialect,
            schemas=schemas,
            engine=self._engine_name,
        )
        return [database]

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
        # TODO handle backends without .list_databases()
        for schema_name in self._backend.list_databases():
            if schema_name.lower() in meta_schemas:
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
        if self._backend is None:
            return []

        try:
            table_names = self._backend.list_tables(
                database=(database, schema)
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

    def get_table_details(
        self, *, table_name: str, schema_name: str, database_name: str
    ) -> Optional[DataTable]:
        """Get a single table from the engine."""
        if self._backend is None:
            return None

        try:
            table = self._backend.table(
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
            marimo_dtype = "integer"
        # numeric is a superset of integer, so we evaluate after is_integer
        elif ibis_dtype.is_numeric():
            marimo_dtype = "number"

        elif ibis_dtype.is_date():
            marimo_dtype = "date"

        elif ibis_dtype.is_timestamp():
            marimo_dtype = "datetime"

        # NOTE handle ibis_dtype.is_time() which doesn't have a date part
        elif ibis_dtype.is_time():
            marimo_dtype = "datetime"

        elif ibis_dtype.is_boolean():
            marimo_dtype = "boolean"

        elif ibis_dtype.is_string():
            marimo_dtype = "string"

        elif ibis_dtype.is_binary():
            marimo_dtype = "string"

        else:
            raise IbisToMarimoConversionError

        return marimo_dtype

    def _resolve_should_auto_discover(
        self,
        value: Union[bool, Literal["auto"]],
    ) -> bool:
        if value == "auto":
            return self._is_cheap_discovery()
        return value

    def _is_cheap_discovery(self) -> bool:
        return self.dialect.lower() in (
            "duckdb",
            "sqlite",
            "mysql",
            "postgresql",
        )
