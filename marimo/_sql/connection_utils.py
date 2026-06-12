# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._data.models import (
    CatalogNode,
    DataSourceConnection,
    DataTable,
    Namespace,
    Schema,
)
from marimo._messaging.notification import SQLDatabaseMetadata, SQLMetadata


def _find_node_by_path(
    nodes: list[CatalogNode], path: list[str]
) -> CatalogNode | None:
    """Descend `path` (segment names) into a catalog tree."""
    if not path:
        return None
    head, *rest = path
    for node in nodes:
        if node.name != head:
            continue
        if not rest:
            return node
        if isinstance(node, Namespace):
            return _find_node_by_path(node.children, rest)
        return None
    return None


def _node_path(metadata: SQLMetadata) -> list[str]:
    if metadata.schema_path:
        return list(metadata.schema_path)
    return [metadata.schema]


def _set_tables_on_node(
    node: Schema | Namespace, tables: list[DataTable]
) -> None:
    if isinstance(node, Schema):
        node.tables = tables
        node.tables_resolved = True
        return
    non_tables = [
        child for child in node.children if not isinstance(child, DataTable)
    ]
    node.children = [*non_tables, *tables]
    node.tables_resolved = True


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

            node = _find_node_by_path(
                database.children, _node_path(sql_metadata)
            )
            if isinstance(node, Schema):
                for i, table in enumerate(node.tables):
                    if table.name == updated_table.name:
                        node.tables[i] = updated_table
                        return
            elif isinstance(node, Namespace):
                for i, child in enumerate(node.children):
                    if (
                        isinstance(child, DataTable)
                        and child.name == updated_table.name
                    ):
                        node.children[i] = updated_table
                        return
            return


def update_schema_list_in_connection(
    connections: list[DataSourceConnection],
    sql_db_metadata: SQLDatabaseMetadata,
    updated_schema_list: list[CatalogNode],
) -> None:
    """Update catalog children in the connection hierarchy, updates in-place.

    When `schema_path` is empty the database's top-level `children` are
    replaced; otherwise the `children` of the `Namespace` at that path are
    replaced.

    Args:
        connections: List of data source connections
        sql_db_metadata: SQL database metadata containing connection, database info
        updated_schema_list: Nodes to replace the existing children with
    """
    for connection in connections:
        if connection.name != sql_db_metadata.connection:
            continue

        for database in connection.databases:
            if database.name != sql_db_metadata.database:
                continue

            if sql_db_metadata.schema_path:
                parent = _find_node_by_path(
                    database.children, sql_db_metadata.schema_path
                )
                if not isinstance(parent, Namespace):
                    return
                parent.children = updated_schema_list
                parent.children_resolved = True
            else:
                database.children = updated_schema_list
                database.children_resolved = True
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

            node = _find_node_by_path(
                database.children, _node_path(sql_metadata)
            )
            if isinstance(node, (Schema, Namespace)):
                _set_tables_on_node(node, updated_table_list)
            return
