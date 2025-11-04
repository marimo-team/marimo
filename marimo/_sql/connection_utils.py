# Copyright 2025 Marimo. All rights reserved.

from marimo._data.models import DataSourceConnection, DataTable
from marimo._messaging.ops import SQLMetadata


def update_table_in_connection(
    connections: list[DataSourceConnection],
    sql_metadata: SQLMetadata,
    updated_table: DataTable,
) -> None:
    """Update a table in the connection hierarchy in-place

    Args:
        connections: List of data source connections
        sql_metadata: SQL metadata containing connection, database, schema info
        updated_table: The updated table to replace the existing one
    """
    for connection in connections:
        if connection.name != sql_metadata.connection:
            continue

        for database in connection.databases:
            if database.name != sql_metadata.database:
                continue

            for schema in database.schemas:
                if schema.name != sql_metadata.schema:
                    continue

                for i, table in enumerate(schema.tables):
                    if table.name == updated_table.name:
                        schema.tables[i] = updated_table
                        return


def update_table_list_in_connection(
    connections: list[DataSourceConnection],
    sql_metadata: SQLMetadata,
    updated_table_list: list[DataTable],
) -> None:
    """Update a list of tables in the connection hierarchy, updates in-place.

    Args:
        connections: List of data source connections
        sql_metadata: SQL metadata containing connection, database, schema info
        updated_table_list: The updated list of tables to replace the existing ones
    """
    for connection in connections:
        if connection.name != sql_metadata.connection:
            continue

        for database in connection.databases:
            if database.name != sql_metadata.database:
                continue

            for schema in database.schemas:
                if schema.name != sql_metadata.schema:
                    continue

                schema.tables = updated_table_list
                return
