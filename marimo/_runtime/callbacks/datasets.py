# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from marimo import _loggers
from marimo._data.preview_column import (
    get_column_preview_for_dataframe,
    get_column_preview_for_duckdb,
)
from marimo._messaging.notification import (
    CatalogChildrenPreviewNotification,
    DataColumnPreviewNotification,
    DataSourceConnectionsNotification,
    SQLCatalogMetadata,
    SQLMetadata,
    SQLTablePreviewNotification,
)
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.commands import (
    ListCatalogChildrenCommand,
    ListDataSourceConnectionCommand,
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
        router.register(
            ListCatalogChildrenCommand, self.preview_catalog_children
        )
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
        schema_path = request.schema_path
        sql_metadata = SQLMetadata(
            connection=variable_name,
            database=database_name,
            schema=schema_name,
            schema_path=schema_path,
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
                schema_path=schema_path,
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

    @kernel_tracer.start_as_current_span("preview_catalog_children")
    async def preview_catalog_children(
        self, request: ListCatalogChildrenCommand
    ) -> None:
        """Get immediate catalog children for a database path."""
        variable_name = cast(VariableName, request.engine)
        database_name = request.database
        catalog_path = request.catalog_path
        sql_catalog_metadata = SQLCatalogMetadata(
            connection=variable_name,
            database=database_name,
            catalog_path=catalog_path,
        )

        engine, error = self.get_engine_catalog(variable_name)
        if error is not None or engine is None:
            broadcast_notification(
                CatalogChildrenPreviewNotification(
                    request_id=request.request_id,
                    children=[],
                    error=error,
                    metadata=sql_catalog_metadata,
                ),
            )
            return

        try:
            children = engine.get_catalog_children(
                database=database_name,
                catalog_path=catalog_path,
                include_table_details=False,
            )
            broadcast_notification(
                CatalogChildrenPreviewNotification(
                    request_id=request.request_id,
                    children=children,
                    metadata=sql_catalog_metadata,
                ),
            )
        except Exception as e:
            LOGGER.exception(
                "Failed to get catalog children for database %s at path %s",
                database_name,
                catalog_path,
            )
            broadcast_notification(
                CatalogChildrenPreviewNotification(
                    request_id=request.request_id,
                    children=[],
                    error="Failed to get catalog children: " + str(e),
                    metadata=sql_catalog_metadata,
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
