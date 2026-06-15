# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._data.models import (
    CatalogNode,
    DataSourceConnection,
    DataTable,
    Namespace,
    Schema,
)
from marimo._messaging.notification import SQLCatalogMetadata, SQLMetadata


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
    if metadata.schema:
        return [metadata.schema]
    return []


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

            path = _node_path(sql_metadata)
            if not path:
                for i, child in enumerate(database.children):
                    if (
                        isinstance(child, DataTable)
                        and child.name == updated_table.name
                    ):
                        database.children[i] = updated_table
                        return
                return

            node = _find_node_by_path(database.children, path)
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


def update_catalog_children_in_connection(
    connections: list[DataSourceConnection],
    sql_catalog_metadata: SQLCatalogMetadata,
    updated_children: list[CatalogNode],
) -> None:
    """Update catalog children at a database path, in-place."""
    for connection in connections:
        if connection.name != sql_catalog_metadata.connection:
            continue

        for database in connection.databases:
            if database.name != sql_catalog_metadata.database:
                continue

            path = sql_catalog_metadata.catalog_path
            if not path:
                database.children = updated_children
                return

            node = _find_node_by_path(database.children, path)
            if isinstance(node, Schema):
                node.tables = [
                    child
                    for child in updated_children
                    if isinstance(child, DataTable)
                ]
            elif isinstance(node, Namespace):
                node.children = updated_children
            return
