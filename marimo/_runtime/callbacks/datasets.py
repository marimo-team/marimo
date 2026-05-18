# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from marimo import _loggers
from marimo._data.preview_column import (
    get_column_preview_for_dataframe,
    get_column_preview_for_duckdb,
)
from marimo._messaging.notification import (
    DataColumnPreviewNotification,
    DataSourceConnectionsNotification,
    SQLDatabaseMetadata,
    SQLMetadata,
    SQLSchemaListPreviewNotification,
    SQLTableListPreviewNotification,
    SQLTablePreviewNotification,
)
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.commands import (
    ListDataSourceConnectionCommand,
    ListSQLSchemasCommand,
    ListSQLTablesCommand,
    PreviewDatasetColumnCommand,
    PreviewSQLTableCommand,
)
from marimo._sql.engines.types import EngineCatalog
from marimo._sql.get_engines import engine_to_data_source_connection
from marimo._tracer import kernel_tracer
from marimo._types.ids import VariableName
from marimo._utils.assert_never import assert_never

if TYPE_CHECKING:
    from marimo._runtime.request_router import RequestRouter
    from marimo._runtime.runtime import Kernel

LOGGER = _loggers.marimo_logger()


class DatasetCallbacks:
    def __init__(self, kernel: Kernel):
        self._kernel = kernel

    def register(self, router: RequestRouter) -> None:
        router.register(
            PreviewDatasetColumnCommand, self.preview_dataset_column
        )
        router.register(PreviewSQLTableCommand, self.preview_sql_table)
        router.register(ListSQLTablesCommand, self.preview_sql_table_list)
        router.register(ListSQLSchemasCommand, self.preview_sql_schema_list)
        router.register(
            ListDataSourceConnectionCommand,
            self.preview_datasource_connection,
        )

    def get_engine_catalog(
        self, variable_name: str
    ) -> tuple[EngineCatalog[Any] | None, str | None]:
        """Get engines that support catalog operations.
        Returns an error if the connection does not support catalog operations."""
        variable_name = cast(VariableName, variable_name)
        connection, error = self._kernel.get_sql_connection(variable_name)
        if error is not None or connection is None:
            return None, error

        if isinstance(connection, EngineCatalog):
            return connection, None
        else:
            return None, "Connection does not support catalog operations"

    @kernel_tracer.start_as_current_span("preview_dataset_column")
    async def preview_dataset_column(
        self, request: PreviewDatasetColumnCommand
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
                broadcast_notification(
                    DataColumnPreviewNotification(
                        error="Column preview for connection data sources is not supported",
                        column_name=column_name,
                        table_name=table_name,
                    ),
                )
                return
            elif source_type == "catalog":
                broadcast_notification(
                    DataColumnPreviewNotification(
                        error="Column preview for catalog data sources is not supported",
                        column_name=column_name,
                        table_name=table_name,
                    ),
                )
                return
            else:
                assert_never(source_type)

            if column_preview is None:
                broadcast_notification(
                    DataColumnPreviewNotification(
                        error=f"Column {column_name} not found",
                        column_name=column_name,
                        table_name=table_name,
                    ),
                )
            else:
                broadcast_notification(column_preview)
        except Exception as e:
            LOGGER.warning(
                "Failed to get preview for column %s in table %s",
                column_name,
                table_name,
                exc_info=e,
            )
            broadcast_notification(
                DataColumnPreviewNotification(
                    error=str(e),
                    column_name=column_name,
                    table_name=table_name,
                ),
            )
        return

    @kernel_tracer.start_as_current_span("preview_sql_table")
    async def preview_sql_table(self, request: PreviewSQLTableCommand) -> None:
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
        sql_metadata = SQLMetadata(
            connection=variable_name,
            database=database_name,
            schema=schema_name,
        )

        engine, error = self.get_engine_catalog(variable_name)
        if error is not None or engine is None:
            broadcast_notification(
                SQLTablePreviewNotification(
                    request_id=request.request_id,
                    table=None,
                    error=error,
                    metadata=sql_metadata,
                ),
            )
            return

        try:
            table = engine.get_table_details(
                table_name=table_name,
                schema_name=schema_name,
                database_name=database_name,
            )

            broadcast_notification(
                SQLTablePreviewNotification(
                    request_id=request.request_id,
                    table=table,
                    metadata=sql_metadata,
                ),
            )
        except Exception as e:
            LOGGER.exception(
                "Failed to get preview for table %s in schema %s",
                table_name,
                schema_name,
            )
            broadcast_notification(
                SQLTablePreviewNotification(
                    request_id=request.request_id,
                    table=None,
                    error="Failed to get table details: " + str(e),
                    metadata=sql_metadata,
                ),
            )

    @kernel_tracer.start_as_current_span("preview_sql_table_list")
    async def preview_sql_table_list(
        self, request: ListSQLTablesCommand
    ) -> None:
        """Get a list of tables from an SQL schema

        Args:
            request (ListSQLTablesRequest): The request containing:
                - engine: Name of the SQL engine / connection
                - database: Name of the database
                - schema: Name of the schema
        """
        variable_name = cast(VariableName, request.engine)
        database_name = request.database
        schema_name = request.schema
        sql_metadata = SQLMetadata(
            connection=variable_name,
            database=database_name,
            schema=schema_name,
        )

        engine, error = self.get_engine_catalog(variable_name)
        if error is not None or engine is None:
            broadcast_notification(
                SQLTableListPreviewNotification(
                    request_id=request.request_id,
                    tables=[],
                    error=error,
                    metadata=sql_metadata,
                ),
            )
            return

        try:
            table_list = engine.get_tables_in_schema(
                schema=schema_name,
                database=database_name,
                include_table_details=False,
            )
            broadcast_notification(
                SQLTableListPreviewNotification(
                    request_id=request.request_id,
                    tables=table_list,
                    metadata=sql_metadata,
                ),
            )
        except Exception as e:
            LOGGER.exception(
                "Failed to get table list for schema %s", schema_name
            )
            broadcast_notification(
                SQLTableListPreviewNotification(
                    request_id=request.request_id,
                    tables=[],
                    error="Failed to get table list: " + str(e),
                    metadata=sql_metadata,
                ),
            )

    @kernel_tracer.start_as_current_span("preview_sql_schema_list")
    async def preview_sql_schema_list(
        self, request: ListSQLSchemasCommand
    ) -> None:
        """Get a list of schemas from an SQL database

        Args:
            request (ListSQLSchemasCommand): The request containing:
                - engine: Name of the SQL engine / connection
                - database: Name of the database
        """
        variable_name = cast(VariableName, request.engine)
        database_name = request.database
        sql_db_metadata = SQLDatabaseMetadata(
            connection=variable_name,
            database=database_name,
        )

        engine, error = self.get_engine_catalog(variable_name)
        if error is not None or engine is None:
            broadcast_notification(
                SQLSchemaListPreviewNotification(
                    request_id=request.request_id,
                    schemas=[],
                    error=error,
                    metadata=sql_db_metadata,
                ),
            )
            return

        try:
            schema_list = engine.get_schemas(
                database=database_name,
                include_tables=False,
                include_table_details=False,
            )
            broadcast_notification(
                SQLSchemaListPreviewNotification(
                    request_id=request.request_id,
                    schemas=schema_list,
                    metadata=sql_db_metadata,
                ),
            )
        except Exception as e:
            LOGGER.exception(
                "Failed to get schema list for database %s", database_name
            )
            broadcast_notification(
                SQLSchemaListPreviewNotification(
                    request_id=request.request_id,
                    schemas=[],
                    error="Failed to get schema list: " + str(e),
                    metadata=sql_db_metadata,
                ),
            )

    @kernel_tracer.start_as_current_span("preview_datasource_connection")
    async def preview_datasource_connection(
        self, request: ListDataSourceConnectionCommand
    ) -> None:
        """Broadcasts a datasource connection for a given engine."""
        variable_name = cast(VariableName, request.engine)
        engine, error = self._kernel.get_sql_connection(variable_name)
        if error is not None or engine is None:
            LOGGER.error("Failed to get engine %s: %s", variable_name, error)
            return

        data_source_connection = engine_to_data_source_connection(
            variable_name, engine
        )

        LOGGER.debug(
            "Broadcasting datasource connection for %s engine", variable_name
        )
        broadcast_notification(
            DataSourceConnectionsNotification(
                connections=[data_source_connection],
            ),
        )
