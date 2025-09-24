# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, cast

from marimo import _loggers
from marimo._data.preview_column import (
    get_column_preview_for_dataframe,
    get_column_preview_for_duckdb,
)
from marimo._messaging.ops import (
    DataColumnPreview,
    DataSourceConnections,
    SQLTableListPreview,
    SQLTablePreview,
)
from marimo._runtime.requests import (
    PreviewDatasetColumnRequest,
    PreviewDataSourceConnectionRequest,
    PreviewSQLTableListRequest,
    PreviewSQLTableRequest,
)
from marimo._sql.engines.types import EngineCatalog
from marimo._sql.get_engines import engine_to_data_source_connection
from marimo._tracer import kernel_tracer
from marimo._types.ids import VariableName
from marimo._utils.assert_never import assert_never

if TYPE_CHECKING:
    from marimo._runtime.runtime.kernel import Kernel


ERROR_MSG_CATALOG_OPERATIONS = "Connection does not support catalog operations"
ERROR_MSG_CONNECTION_OPERATIONS = (
    "Connection does not support query or catalog operations"
)

LOGGER = _loggers.marimo_logger()


class DatasetCallbacks:
    def __init__(self, kernel: Kernel):
        self._kernel = kernel

    def get_engine_catalog(
        self, variable_name: str
    ) -> tuple[Optional[EngineCatalog[Any]], Optional[str]]:
        """Get engines that support catalog operations.
        Returns an error if the connection does not support catalog operations."""

        connection, error = self._kernel.get_sql_connection(variable_name)
        if error is not None or connection is None:
            return None, error

        if isinstance(connection, EngineCatalog):
            return connection, None
        else:
            return None, ERROR_MSG_CATALOG_OPERATIONS

    @kernel_tracer.start_as_current_span("preview_dataset_column")
    async def preview_dataset_column(
        self, request: PreviewDatasetColumnRequest
    ) -> None:
        """Preview a column of a dataset.

        The dataset is loaded, and the column is displayed in the frontend.

        Args:
            request (PreviewDatasetColumnRequest): The preview request containing:
                - table_name: Name of the table
                - column_name: Name of the column
                - source_type: Type of data source ("duckdb" or "local")
        """
        table_name = request.table_name
        column_name = request.column_name
        source_type = request.source_type

        try:
            if source_type == "duckdb":
                column_preview = get_column_preview_for_duckdb(
                    fully_qualified_table_name=request.fully_qualified_table_name
                    or table_name,
                    column_name=column_name,
                )
            elif source_type == "local":
                dataset = self._kernel.globals[table_name]
                column_preview = get_column_preview_for_dataframe(
                    dataset, request
                )
            elif source_type == "connection":
                DataColumnPreview(
                    error="Column preview for connection data sources is not supported",
                    column_name=column_name,
                    table_name=table_name,
                ).broadcast()
                return
            elif source_type == "catalog":
                DataColumnPreview(
                    error="Column preview for catalog data sources is not supported",
                    column_name=column_name,
                    table_name=table_name,
                ).broadcast()
                return
            else:
                assert_never(source_type)

            if column_preview is None:
                DataColumnPreview(
                    error=f"Column {column_name} not found",
                    column_name=column_name,
                    table_name=table_name,
                ).broadcast()
            else:
                column_preview.broadcast()
        except Exception as e:
            LOGGER.warning(
                "Failed to get preview for column %s in table %s",
                column_name,
                table_name,
                exc_info=e,
            )
            DataColumnPreview(
                error=str(e),
                column_name=column_name,
                table_name=table_name,
            ).broadcast()
        return

    @kernel_tracer.start_as_current_span("preview_sql_table")
    async def preview_sql_table(self, request: PreviewSQLTableRequest) -> None:
        """Get table details for an SQL table.

        Args:
            request (PreviewSQLTableRequest): The request containing:
                - engine: Name of the SQL engine / connection
                - database: Name of the database
                - schema: Name of the schema
                - table_name: Name of the table
        """
        variable_name = cast(VariableName, request.engine)
        database_name = request.database
        schema_name = request.schema
        table_name = request.table_name

        engine, error = self.get_engine_catalog(variable_name)
        if error is not None or engine is None:
            SQLTablePreview(
                request_id=request.request_id, table=None, error=error
            ).broadcast()
            return

        try:
            table = engine.get_table_details(
                table_name=table_name,
                schema_name=schema_name,
                database_name=database_name,
            )

            SQLTablePreview(
                request_id=request.request_id, table=table
            ).broadcast()
        except Exception as e:
            LOGGER.exception(
                "Failed to get preview for table %s in schema %s",
                table_name,
                schema_name,
            )
            SQLTablePreview(
                request_id=request.request_id,
                table=None,
                error="Failed to get table details: " + str(e),
            ).broadcast()

    @kernel_tracer.start_as_current_span("preview_sql_table_list")
    async def preview_sql_table_list(
        self, request: PreviewSQLTableListRequest
    ) -> None:
        """Get a list of tables from an SQL schema

        Args:
            request (PreviewSQLTableListRequest): The request containing:
                - engine: Name of the SQL engine / connection
                - database: Name of the database
                - schema: Name of the schema
        """
        variable_name = cast(VariableName, request.engine)
        database_name = request.database
        schema_name = request.schema

        engine, error = self.get_engine_catalog(variable_name)
        if error is not None or engine is None:
            SQLTableListPreview(
                request_id=request.request_id, tables=[], error=error
            ).broadcast()
            return

        try:
            table_list = engine.get_tables_in_schema(
                schema=schema_name,
                database=database_name,
                include_table_details=False,
            )
            SQLTableListPreview(
                request_id=request.request_id, tables=table_list
            ).broadcast()
        except Exception as e:
            LOGGER.exception(
                "Failed to get table list for schema %s", schema_name
            )
            SQLTableListPreview(
                request_id=request.request_id,
                tables=[],
                error="Failed to get table list: " + str(e),
            )

    @kernel_tracer.start_as_current_span("preview_datasource_connection")
    async def preview_datasource_connection(
        self, request: PreviewDataSourceConnectionRequest
    ) -> None:
        """Broadcasts a datasource connection for a given engine"""
        variable_name = cast(VariableName, request.engine)
        engine, error = self.get_engine_catalog(variable_name)
        if error is not None or engine is None:
            LOGGER.error("Failed to get engine %s", variable_name)
            return

        data_source_connection = engine_to_data_source_connection(
            variable_name, engine
        )

        LOGGER.debug(
            "Broadcasting datasource connection for %s engine", variable_name
        )
        DataSourceConnections(
            connections=[data_source_connection],
        ).broadcast()
