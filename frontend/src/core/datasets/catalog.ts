/* Copyright 2026 Marimo. All rights reserved. */

import type {
  Database,
  DatabaseNamespace,
  DatabaseSchema,
  DataTable,
} from "@/core/kernel/messages";

export type CatalogNode = Database["children"][number];

/** Empty schema name marks a schemaless catalog node (e.g. ClickHouse, Iceberg). */
export function isSchemaless(schemaName: string): boolean {
  return schemaName === "";
}

export function isSchemaNode(node: CatalogNode): node is DatabaseSchema {
  return node.kind === "schema";
}

export function isNamespaceNode(node: CatalogNode): node is DatabaseNamespace {
  return node.kind === "namespace";
}

export function isDataTableNode(node: CatalogNode): node is DataTable {
  return node.kind === "data_table";
}

export function getSchemaNodes(children: CatalogNode[]): DatabaseSchema[] {
  return children.filter(isSchemaNode);
}

/** Path segment names that locate the node holding tables within a database. */
export function catalogNodePath({
  schema,
  schemaPath,
}: {
  schema: string;
  schemaPath?: string[];
}): string[] {
  if (!schemaPath || schemaPath.length === 0) {
    return [schema];
  }
  if (!schema || schemaPath.at(-1) === schema) {
    return schemaPath;
  }
  return [...schemaPath, schema];
}

export function partitionNamespaceChildren(namespace: DatabaseNamespace): {
  childNodes: CatalogNode[];
  tables: DataTable[];
} {
  const childNodes: CatalogNode[] = [];
  const tables: DataTable[] = [];
  for (const child of namespace.children) {
    if (isDataTableNode(child)) {
      tables.push(child);
    } else {
      childNodes.push(child);
    }
  }
  return { childNodes, tables };
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
          nodes: node.children,
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
    return findNodeAtPath({ nodes: node.children, path: rest });
  }
  return undefined;
}

/** Replace a namespace's table children, leaving sub-namespaces/schemas. */
function withNamespaceTables(
  node: DatabaseNamespace,
  tables: DataTable[],
): DatabaseNamespace {
  const nonTables = node.children.filter((child) => !isDataTableNode(child));
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

/** Replace the resolved table list at `path` (schema or namespace node). */
export function setTablesAtPath({
  nodes,
  path,
  tables,
}: {
  nodes: CatalogNode[];
  path: string[];
  tables: DataTable[];
}): CatalogNode[] {
  return updateNodeAtPath({
    nodes,
    path,
    update: (node) => {
      if (isSchemaNode(node)) {
        return { ...node, tables };
      }
      if (isNamespaceNode(node)) {
        return withNamespaceTables(node, tables);
      }
      return node;
    },
  });
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
  return updateNodeAtPath({
    nodes,
    path,
    update: (node) => {
      if (isSchemaNode(node)) {
        return { ...node, tables: upsertTable(node.tables, table) };
      }
      if (isNamespaceNode(node)) {
        const existingTables = node.children.filter(isDataTableNode);
        return withNamespaceTables(node, upsertTable(existingTables, table));
      }
      return node;
    },
  });
}

export function setChildNodesAtPath({
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
      if (!isNamespaceNode(node)) {
        return node;
      }
      return { ...node, children };
    },
  });
}

export interface CatalogWalkContext {
  databaseName: string;
  segments: string[];
}

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
    const segments =
      isDataTableNode(node) || isSchemaless(node.name)
        ? context.segments
        : [...context.segments, node.name];
    visit({ ...context, segments, node });

    if (isSchemaNode(node) || isDataTableNode(node)) {
      continue;
    }
    if (isNamespaceNode(node)) {
      walkCatalogNodes({
        nodes: node.children,
        context: { ...context, segments },
        visit,
      });
    }
  }
}

export function collectTablesFromNode(node: CatalogNode): DataTable[] {
  if (isSchemaNode(node)) {
    return node.tables;
  }
  if (isDataTableNode(node)) {
    return [node];
  }
  if (isNamespaceNode(node)) {
    return node.children.flatMap(collectTablesFromNode);
  }
  return [];
}
