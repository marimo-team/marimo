# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
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
from marimo._sql.engines.types import InferenceConfig, SQLConnection
from marimo._sql.utils import sql_type_to_data_type, try_convert_to_polars
from marimo._types.ids import VariableName

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from redshift_connector import Connection  # type: ignore


class RedshiftEngine(SQLConnection["Connection"]):
    """Redshift engine."""

    def __init__(
        self,
        connection: Connection,
        engine_name: Optional[VariableName] = None,
    ):
        super().__init__(connection, engine_name)

    @property
    def source(self) -> str:
        return "redshift"

    @property
    def dialect(self) -> str:
        return "redshift"

    @staticmethod
    def is_compatible(var: Any) -> bool:
        if not DependencyManager.redshift_connector.imported():
            return False

        from redshift_connector import Connection

        return isinstance(var, Connection)

    @property
    def inference_config(self) -> InferenceConfig:
        return InferenceConfig(
            auto_discover_schemas=True,
            auto_discover_tables=False,
            auto_discover_columns=False,
        )

    def _try_commit(self) -> None:
        try:
            self._connection.commit()
        except Exception as e:
            LOGGER.debug("Failed to commit. Reason: %s.", e)

    def _try_rollback(self) -> None:
        """
        Rollback the connection to avoid errors with the connection being in a bad state.
        For example, after a query failure
        """
        from redshift_connector.error import ProgrammingError  # type: ignore

        try:
            self._connection.rollback()
        except ProgrammingError as e:
            # Close prepared statements that are left open
            # They can prevent rollbacks
            LOGGER.debug(f"Programming error {e}")
            error_message = ast.literal_eval(str(e))["M"]
            parts = error_message.split('"')
            if len(parts) > 1:
                prepared_statement_name = parts[1]
                statement_bin = self._connection.get_statement_name_bin(
                    prepared_statement_name
                )
                self._connection.close_prepared_statement(
                    statement_name_bin=statement_bin
                )
                LOGGER.debug(
                    f"Closing prepared statement {prepared_statement_name}"
                )
                self._connection.rollback()
        except Exception as e:
            LOGGER.debug("Failed to rollback. Reason: %s.", e)

    def execute(self, query: str) -> Any:
        sql_output_format = self.sql_output_format()

        with self._connection.cursor() as cursor:
            self._try_rollback()

            if sql_output_format == "auto":
                if DependencyManager.polars.has():
                    sql_output_format = "polars"
                else:
                    sql_output_format = "pandas"

            if sql_output_format in ("polars", "lazy-polars"):
                result, error = try_convert_to_polars(
                    query=query,
                    connection=cursor,
                    lazy=sql_output_format == "lazy-polars",
                )
                if error is None:
                    self._try_commit()
                    return result

                LOGGER.warning(
                    "Failed to convert to polars. Reason: %s.", error
                )
                DependencyManager.pandas.require("to convert this data")
                # Fall back to pandas
                sql_output_format = "pandas"

            cursor_result = cursor.execute(query)
            self._try_commit()

            if sql_output_format == "native":
                return cursor_result
            if sql_output_format == "pandas":
                return cursor_result.fetch_dataframe()
            return cursor_result

    def get_default_database(self) -> Optional[str]:
        with self._connection.cursor() as cursor:
            try:
                return str(cursor.cur_catalog())
            except Exception as e:
                LOGGER.debug("Failed to get default database. Reason: %s.", e)
                return None

    def get_default_schema(self) -> Optional[str]:
        with self._connection.cursor() as cursor:
            try:
                result = cursor.execute("SELECT current_schema()")
                return str(result.fetchone()[0])
            except Exception as e:
                LOGGER.debug("Failed to get default schema. Reason: %s.", e)
                return None

    def get_databases(
        self,
        *,
        include_schemas: Union[bool, Literal["auto"]],
        include_tables: Union[bool, Literal["auto"]],
        include_table_details: Union[bool, Literal["auto"]],
    ) -> list[Database]:
        """Get catalogs from the engine. Redshift only supports one catalog per connection.

        Catalogs -> Schemas -> Tables
        """

        with self._connection.cursor() as cursor:
            try:
                # get_catalogs only returns current catalog
                catalog = cursor.get_catalogs()[0][0]
            except Exception as e:
                LOGGER.debug("Failed to get catalogs. Reason: %s.", e)
                return []

            databases: list[Database] = []

            include_schemas = self._resolve_should_auto_discover(
                include_schemas
            )
            include_tables = self._resolve_should_auto_discover(include_tables)
            include_table_details = self._resolve_should_auto_discover(
                include_table_details
            )

            schemas: list[Schema] = []
            if include_schemas:
                schemas = self.get_schemas(
                    catalog=catalog,
                    include_tables=include_tables,
                    include_table_details=include_table_details,
                )

            databases.append(
                Database(
                    name=catalog,
                    dialect=self.dialect,
                    schemas=schemas,
                    engine=self._engine_name,
                )
            )

            return databases

    def get_schemas(
        self,
        *,
        catalog: str,
        include_tables: bool,
        include_table_details: bool,
    ) -> list[Schema]:
        """Get schemas from the engine."""

        output_schemas: list[Schema] = []
        with self._connection.cursor() as cursor:
            # get_schemas returns [["schema_name", "catalog"], ["schema_2", "catalog"]]
            schemas = cursor.get_schemas(catalog=catalog)

            for schema in schemas:
                schema_name = schema[0]
                if schema_name == "information_schema":  # Skip meta-schemas
                    continue

                tables = (
                    self.get_tables_in_schema(
                        schema=schema_name,
                        database=catalog,
                        include_table_details=include_table_details,
                    )
                    if include_tables
                    else []
                )
                output_schemas.append(Schema(name=schema_name, tables=tables))

            return output_schemas

    def get_tables_in_schema(
        self, *, schema: str, database: str, include_table_details: bool
    ) -> list[DataTable]:
        """Get tables from the engine. Databases are treated as catalogs."""

        output_tables: list[DataTable] = []

        with self._connection.cursor() as cursor:
            # get_tables returns [["catalog", "schema", "table_name", "table_type (VIEW / TABLE)", None, "", ...]]
            try:
                tables = cursor.get_tables(
                    catalog=database, schema_pattern=schema
                )
            except Exception as e:
                LOGGER.debug("Failed to get tables. Reason: %s.", e)
                return []

            for table in tables:
                table_name, table_type = table[2], table[3]
                table_type = self._resolve_table_type(table_type)

                # If we are satisfied with this info, we can return
                if not include_table_details:
                    output_tables.append(
                        DataTable(
                            source_type="connection",
                            source=self.dialect,
                            name=table_name,
                            num_rows=None,
                            num_columns=None,
                            variable_name=None,
                            engine=self._engine_name,
                            type=table_type,
                            columns=[],
                            primary_keys=[],
                            indexes=[],
                        )
                    )
                    continue

                detailed_table = self.get_table_details(
                    table_name=table_name,
                    schema_name=schema,
                    database_name=database,
                )
                if detailed_table is not None:
                    output_tables.append(detailed_table)
            return output_tables

    def _get_columns_api(
        self,
        *,
        catalog: str,
        schema_name: str,
        table_name: str,
    ) -> tuple[tuple[str, ...], ...]:
        """The API is unreliable hence this method is not preferred"""
        columns: tuple[tuple[str, ...], ...] = ()
        with self._connection.cursor() as cursor:
            try:
                # get_columns returns:
                # [[catalog, schema, table_name, column_name, unknown, data type, unknown, ...], ...]
                columns = cursor.get_columns(
                    catalog=catalog,
                    schema_pattern=schema_name,
                    tablename_pattern=table_name,
                )
            except Exception as e:
                LOGGER.debug(
                    f"Failed to get columns for {catalog}.{schema_name}.{table_name} Reason: {e}"
                )
            return columns

    def get_table_details(
        self, *, table_name: str, schema_name: str, database_name: str
    ) -> Optional[DataTable]:
        """Get detailed metadata for a given table in a database."""

        with self._connection.cursor() as cursor:
            try:
                table = cursor.get_tables(
                    catalog=database_name,
                    schema_pattern=schema_name,
                    table_name_pattern=table_name,
                )
            except Exception as e:
                LOGGER.debug("Failed to get table. Reason: %s.", e)
                return None

            table_type = self._resolve_table_type(table[0][3])

            row_count = cursor.execute(
                f"SELECT COUNT(*) FROM {database_name}.{schema_name}.{table_name}"
            )
            num_rows = row_count.fetchone()[0]

            try:
                # [[catalog, schema, table_name, column_name, ordinal_position, column_default, is_nullable, data_type, character_maximum_length, numeric_precision, numeric_scale, remarks]]
                columns = cursor.execute(
                    f"SHOW COLUMNS FROM TABLE {database_name}.{schema_name}.{table_name};"
                )
            except Exception as e:
                LOGGER.debug(
                    f"Failed to get columns for {database_name}.{schema_name}.{table_name}. Reason: {e}"
                )
                columns = []

            cols: list[DataTableColumn] = []
            for col in columns:
                col_name, col_type = col[3], col[7]
                data_type = self._get_data_type(
                    col_type
                ) or sql_type_to_data_type(col_type)
                cols.append(
                    DataTableColumn(
                        name=col_name,
                        type=data_type,
                        external_type=str(col_type),
                        sample_values=[],
                    )
                )

            # get_primary_keys returns:
            # [[catalog, schema, table_name, column_name, key_seq, pk_name], ...]
            primary_keys = cursor.get_primary_keys(
                catalog=database_name, schema=schema_name, table=table_name
            )

            primary_keys = [pk[3] for pk in primary_keys]

            return DataTable(
                source_type="connection",
                source=self.dialect,
                name=table_name,
                num_rows=num_rows,
                num_columns=len(cols),
                variable_name=None,
                engine=self._engine_name,
                type=table_type,
                columns=cols,
                primary_keys=primary_keys,
                indexes=[],
            )

    def _resolve_table_type(self, table_type: str) -> DataTableType:
        return "view" if table_type == "VIEW" else "table"

    def _get_data_type(self, data_type: str) -> Optional[DataType]:
        data_type = data_type.lower()
        if "cardinal_number" in data_type:
            return "number"
        elif "character_data" in data_type:
            return "string"
        return None

    def _resolve_should_auto_discover(
        self, value: Union[bool, Literal["auto"]]
    ) -> bool:
        # Opt to not auto-discover for now
        if value == "auto":
            return False
        return value
