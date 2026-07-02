# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._data.models import (
    Database,
    DataSourceConnection,
    DataTable,
    Schema,
)
from marimo._messaging.notification import SQLDatabaseMetadata, SQLMetadata


def _find_database(
    connections: list[DataSourceConnection],
    connection_name: str,
    database_name: str,
) -> Database | None:
    for connection in connections:
        if connection.name != connection_name:
            continue
        for database in connection.databases:
            if database.name == database_name:
                return database
    return None


def _find_schema_by_path(
    schemas: list[Schema], path: list[str]
) -> Schema | None:
    """Descend `path` (segment names) into nested schema lists."""
    if not path:
        return None
    head, *rest = path
    for schema in schemas:
        if schema.name == head:
            if not rest:
                return schema
            return _find_schema_by_path(schema.child_schemas, rest)
    return None


def _find_table_schema(
    database: Database, sql_metadata: SQLMetadata
) -> Schema | None:
    """Locate the schema holding a table. For nested schemas it is found by
    descending `schema_path`; otherwise by schema name."""
    if sql_metadata.schema_path:
        return _find_schema_by_path(database.schemas, sql_metadata.schema_path)
    for schema in database.schemas:
        if schema.name == sql_metadata.schema:
            return schema
    return None


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
    database = _find_database(
        connections, sql_metadata.connection, sql_metadata.database
    )
    if database is None:
        return
    schema = _find_table_schema(database, sql_metadata)
    if schema is None:
        return
    for i, table in enumerate(schema.tables):
        if table.name == updated_table.name:
            schema.tables[i] = updated_table
            return


def update_schema_list_in_connection(
    connections: list[DataSourceConnection],
    sql_db_metadata: SQLDatabaseMetadata,
    updated_schema_list: list[Schema],
) -> None:
    """Update a list of schemas in the connection hierarchy, updates in-place.

    When `schema_path` is empty the database's top-level schemas are replaced;
    otherwise the child schemas of the schema at that path are replaced.

    Args:
        connections: List of data source connections
        sql_db_metadata: SQL database metadata containing connection, database info
        updated_schema_list: The updated list of schemas to replace the existing ones
    """
    database = _find_database(
        connections, sql_db_metadata.connection, sql_db_metadata.database
    )
    if database is None:
        return
    if sql_db_metadata.schema_path:
        parent = _find_schema_by_path(
            database.schemas, sql_db_metadata.schema_path
        )
        if parent is None:
            return
        parent.child_schemas = updated_schema_list
        parent.child_schemas_resolved = True
        return
    database.schemas = updated_schema_list
    database.schemas_resolved = True


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
    database = _find_database(
        connections, sql_metadata.connection, sql_metadata.database
    )
    if database is None:
        return
    schema = _find_table_schema(database, sql_metadata)
    if schema is None:
        return
    schema.tables = updated_table_list
    schema.tables_resolved = True
