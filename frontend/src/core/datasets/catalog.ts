/* Copyright 2026 Marimo. All rights reserved. */

import type {
  Database,
  DatabaseNamespace,
  DatabaseSchema,
  DataTable,
} from "@/core/kernel/messages";

export type CatalogNode = NonNullable<Database["children"]>[number];

export function isSchemaNode(node: CatalogNode): node is DatabaseSchema {
  return node.kind === "schema";
}

export function isNamespaceNode(node: CatalogNode): node is DatabaseNamespace {
  return node.kind === "namespace";
}

export function isDataTableNode(node: CatalogNode): node is DataTable {
  return node.kind === "data_table";
}

/**
 * A `children`/`tables` bucket is deferred when it has not been discovered yet
 * and should be fetched lazily on expand. An empty array means it was
 * discovered and is genuinely empty; a non-empty array holds the nodes.
 */
export function isDeferred<T>(
  bucket: T[] | null | undefined,
): bucket is null | undefined {
  return bucket == null;
}

export function getSchemaNodes(children: CatalogNode[]): DatabaseSchema[] {
  return children.filter(isSchemaNode);
}

/**
 * Normalize `schema` and an optional namespace `catalogPath` into the segment
 * names used to locate the catalog node that owns a table list.
 *
 * Flat SQL databases use `schema` alone (e.g. `["public"]`). An empty `schema`
 * means tables live at the database root (`[]`).
 *
 * Nested catalogs pass the namespace segments already resolved while browsing.
 * When the target is a schema under that path, `schema` is appended unless it
 * is already the final segment.
 */
export function catalogNodePath({
  schema,
  catalogPath,
}: {
  schema: string;
  catalogPath?: string[];
}): string[] {
  if (!catalogPath || catalogPath.length === 0) {
    return schema ? [schema] : [];
  }
  if (!schema || catalogPath.at(-1) === schema) {
    return catalogPath;
  }
  return [...catalogPath, schema];
}

/**
 * Partition `children` into child nodes and tables.
 *
 * @param children - The children of a database or namespace.
 * @returns An object containing two arrays:
 * - `childNodes`: The child nodes of the database or namespace.
 * - `tables`: The tables in the database or namespace.
 */
export function partitionCatalogChildren(children: CatalogNode[]): {
  childNodes: CatalogNode[];
  tables: DataTable[];
} {
  const childNodes: CatalogNode[] = [];
  const tables: DataTable[] = [];
  for (const child of children) {
    if (isDataTableNode(child)) {
      tables.push(child);
    } else {
      childNodes.push(child);
    }
  }
  return { childNodes, tables };
}

function tableNameMatchesSearch(tableName: string, query: string): boolean {
  return tableName.toLowerCase().includes(query);
}

/**
 * Whether a loaded catalog subtree contains a table whose name matches
 * `searchValue`. Returns false for deferred buckets (not yet fetched).
 */
export function catalogSubtreeMatchesSearch(
  node: CatalogNode,
  searchValue: string,
): boolean {
  const query = searchValue.trim().toLowerCase();
  if (!query) {
    return false;
  }

  if (isDataTableNode(node)) {
    return tableNameMatchesSearch(node.name, query);
  }

  if (isSchemaNode(node)) {
    if (isDeferred(node.tables)) {
      return false;
    }
    return node.tables.some((table) =>
      tableNameMatchesSearch(table.name, query),
    );
  }

  if (isNamespaceNode(node)) {
    if (isDeferred(node.children)) {
      return false;
    }
    const { childNodes, tables } = partitionCatalogChildren(node.children);
    if (tables.some((table) => tableNameMatchesSearch(table.name, query))) {
      return true;
    }
    return childNodes.some((child) =>
      catalogSubtreeMatchesSearch(child, searchValue),
    );
  }

  return false;
}

/** Whether any resolved child under `children` contains a matching table. */
export function catalogChildrenMatchSearch(
  children: CatalogNode[],
  searchValue: string,
): boolean {
  const query = searchValue.trim();
  if (!query) {
    return false;
  }
  return children.some((node) => catalogSubtreeMatchesSearch(node, query));
}

/** Auto-expand a schema/namespace row during search when its loaded subtree matches. */
export function shouldExpandCatalogNodeForSearch(
  node: DatabaseSchema | DatabaseNamespace,
  searchValue: string | undefined,
): boolean {
  const query = searchValue?.trim();
  if (!query) {
    return false;
  }
  const bucket = isNamespaceNode(node) ? node.children : node.tables;
  if (isDeferred(bucket)) {
    return false;
  }
  return catalogSubtreeMatchesSearch(node, query);
}

/** Auto-expand a database row during search when its loaded children match. */
export function shouldExpandDatabaseForSearch(
  children: CatalogNode[] | null | undefined,
  searchValue: string | undefined,
): boolean {
  const query = searchValue?.trim();
  if (!query || isDeferred(children)) {
    return false;
  }
  return catalogChildrenMatchSearch(children ?? [], query);
}

/**
 * Immutably descend `path` (node names) into a catalog tree and apply
 * `update` to the matching node. Intermediate segments must be namespaces.
 */
export function updateNodeAtPath({
  nodes,
  path,
  update,
}: {
  nodes: CatalogNode[];
  path: string[];
  update: (node: CatalogNode) => CatalogNode;
}): CatalogNode[] {
  if (path.length === 0) {
    return nodes;
  }
  const [head, ...rest] = path;
  return nodes.map((node) => {
    if (node.name !== head) {
      return node;
    }
    if (rest.length === 0) {
      return update(node);
    }
    if (isNamespaceNode(node)) {
      return {
        ...node,
        children: updateNodeAtPath({
          nodes: node.children ?? [],
          path: rest,
          update,
        }),
      };
    }
    return node;
  });
}

export function findNodeAtPath({
  nodes,
  path,
}: {
  nodes: CatalogNode[];
  path: string[];
}): CatalogNode | undefined {
  if (path.length === 0) {
    return undefined;
  }
  const [head, ...rest] = path;
  const node = nodes.find((child) => child.name === head);
  if (!node) {
    return undefined;
  }
  if (rest.length === 0) {
    return node;
  }
  if (isNamespaceNode(node)) {
    return findNodeAtPath({ nodes: node.children ?? [], path: rest });
  }
  return undefined;
}

/** Replace a namespace's table children, leaving sub-namespaces/schemas. */
function withNamespaceTables(
  node: DatabaseNamespace,
  tables: DataTable[],
): DatabaseNamespace {
  const nonTables = (node.children ?? []).filter(
    (child) => !isDataTableNode(child),
  );
  return { ...node, children: [...nonTables, ...tables] };
}

/** Upsert `table` into a list by name, appending when absent. */
function upsertTable(tables: DataTable[], table: DataTable): DataTable[] {
  if (tables.length === 0) {
    return [table];
  }
  let found = false;
  const updated = tables.map((t) => {
    if (t.name === table.name) {
      found = true;
      return table;
    }
    return t;
  });
  return found ? updated : [...updated, table];
}

/** Upsert a single table (by name) into the node at `path`. */
export function mergeTableAtPath({
  nodes,
  path,
  table,
}: {
  nodes: CatalogNode[];
  path: string[];
  table: DataTable;
}): CatalogNode[] {
  if (path.length === 0) {
    const nonTables = nodes.filter((child) => !isDataTableNode(child));
    const existingTables = nodes.filter(isDataTableNode);
    return [...nonTables, ...upsertTable(existingTables, table)];
  }
  return updateNodeAtPath({
    nodes,
    path,
    update: (node) => {
      if (isSchemaNode(node)) {
        return { ...node, tables: upsertTable(node.tables ?? [], table) };
      }
      if (isNamespaceNode(node)) {
        const existingTables = (node.children ?? []).filter(isDataTableNode);
        return withNamespaceTables(node, upsertTable(existingTables, table));
      }
      return node;
    },
  });
}

/** Replace the immediate catalog children at `path`. */
export function setCatalogChildrenAtPath({
  nodes,
  path,
  children,
}: {
  nodes: CatalogNode[];
  path: string[];
  children: CatalogNode[];
}): CatalogNode[] {
  if (path.length === 0) {
    return children;
  }
  return updateNodeAtPath({
    nodes,
    path,
    update: (node) => {
      if (isSchemaNode(node)) {
        return { ...node, tables: children.filter(isDataTableNode) };
      }
      if (isNamespaceNode(node)) {
        return { ...node, children };
      }
      return node;
    },
  });
}

export interface CatalogWalkContext {
  databaseName: string;
  segments: string[];
}

/**
 * Depth-first walk over catalog nodes.
 *
 * Invokes `visit` for each node. `segments` in the context is the
 * namespace/schema path from the database root to the node's container.
 * Inline data tables inherit their parent's path (the table name is not
 * appended). Namespaces are recursed into; schemas and data tables are
 * leaves — callers read `node.tables` for a schema's table list.
 *
 * @param nodes - Catalog children to traverse (e.g. a database's `children`).
 * @param context - Walk state passed to each `visit` call.
 * @param context.databaseName - Name of the database being walked.
 * @param context.segments - Path to the current container, relative to the database.
 * @param visit - Callback invoked for each node with updated `segments` and the `node`.
 */
export function walkCatalogNodes({
  nodes,
  context,
  visit,
}: {
  nodes: CatalogNode[];
  context: CatalogWalkContext;
  visit: (ctx: CatalogWalkContext & { node: CatalogNode }) => void;
}): void {
  for (const node of nodes) {
    const segments = isDataTableNode(node)
      ? context.segments
      : [...context.segments, node.name];
    visit({ ...context, segments, node });

    if (isSchemaNode(node) || isDataTableNode(node)) {
      continue;
    }
    if (isNamespaceNode(node)) {
      walkCatalogNodes({
        nodes: node.children ?? [],
        context: { ...context, segments },
        visit,
      });
    }
  }
}

export function collectTablesFromNode(node: CatalogNode): DataTable[] {
  if (isSchemaNode(node)) {
    return node.tables ?? [];
  }
  if (isDataTableNode(node)) {
    return [node];
  }
  if (isNamespaceNode(node)) {
    return (node.children ?? []).flatMap(collectTablesFromNode);
  }
  return [];
}
