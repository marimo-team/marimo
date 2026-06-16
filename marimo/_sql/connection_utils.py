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
            return _find_node_by_path(node.children or [], rest)
        return None
    return None


def _node_path(metadata: SQLMetadata) -> list[str]:
    if metadata.catalog_path:
        return list(metadata.catalog_path)
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
                for i, child in enumerate(database.children or []):
                    if (
                        isinstance(child, DataTable)
                        and child.name == updated_table.name
                    ):
                        database.children[i] = updated_table  # type: ignore[index]
                        return
                return

            node = _find_node_by_path(database.children or [], path)
            if isinstance(node, Schema):
                for i, table in enumerate(node.tables or []):
                    if table.name == updated_table.name:
                        node.tables[i] = updated_table  # type: ignore[index]
                        return
            elif isinstance(node, Namespace):
                for i, child in enumerate(node.children or []):
                    if (
                        isinstance(child, DataTable)
                        and child.name == updated_table.name
                    ):
                        node.children[i] = updated_table  # type: ignore[index]
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

            node = _find_node_by_path(database.children or [], path)
            if isinstance(node, Schema):
                node.tables = [
                    child
                    for child in updated_children
                    if isinstance(child, DataTable)
                ]
            elif isinstance(node, Namespace):
                node.children = updated_children
            return


def _merge_node(old: CatalogNode, new: CatalogNode) -> CatalogNode:
    """Merge `new` onto `old` of the same kind, preserving loaded subtrees."""
    if isinstance(new, Schema) and isinstance(old, Schema):
        new.tables = new.tables if new.tables is not None else old.tables
    elif isinstance(new, Namespace) and isinstance(old, Namespace):
        new.children = merge_catalog_children(old.children, new.children)
    return new


def merge_catalog_children(
    prev: list[CatalogNode] | None,
    new: list[CatalogNode] | None,
) -> list[CatalogNode] | None:
    """Merge a freshly introspected child list into the previous one.

    A deferred refresh keeps whatever we already discovered so a shallow
    re-introspection does not drop lazily loaded subtrees; otherwise nodes are
    merged by name (recursing into containers) following the new payload's
    membership and order.
    """
    if new is None:
        return prev
    if prev is None:
        return new
    prev_by_name = {node.name: node for node in prev}
    merged: list[CatalogNode] = []
    for node in new:
        old = prev_by_name.get(node.name)
        merged.append(_merge_node(old, node) if old is not None else node)
    return merged


def merge_data_source_connection(
    prev: DataSourceConnection, new: DataSourceConnection
) -> DataSourceConnection:
    """Merge a refreshed connection onto the previous one.

    Preserves lazily loaded catalog subtrees across periodic re-introspection
    (see `merge_catalog_children`). Mutates and returns `new`.
    """
    prev_databases = {db.name: db for db in prev.databases}
    for database in new.databases:
        old = prev_databases.get(database.name)
        if old is not None:
            database.children = merge_catalog_children(
                old.children, database.children
            )
    return new
