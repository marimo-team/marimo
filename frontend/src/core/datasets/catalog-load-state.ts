/* Copyright 2026 Marimo. All rights reserved. */

import type { DataSourceConnection as BackendDataSourceConnection } from "../kernel/messages";
import {
  type CatalogNode,
  catalogNodePath,
  isDataTableNode,
  isNamespaceNode,
  isSchemaNode,
} from "./catalog";

export interface CatalogLoadState {
  childrenLoaded: ReadonlySet<string>;
  tablesLoaded: ReadonlySet<string>;
}

export function emptyCatalogLoadState(): CatalogLoadState {
  return {
    childrenLoaded: new Set(),
    tablesLoaded: new Set(),
  };
}

export function catalogPathKey(database: string, segments: string[]): string {
  return JSON.stringify([database, ...segments.filter(Boolean)]);
}

function markCatalogPathLoaded({
  childrenLoaded,
  tablesLoaded,
  database,
  path,
}: {
  childrenLoaded: Set<string>;
  tablesLoaded: Set<string>;
  database: string;
  path: string[];
}): void {
  const key = catalogPathKey(database, path);
  childrenLoaded.add(key);
  tablesLoaded.add(key);
}

/** Union hydrated load keys with prior frontend state from catalog fetches. */
export function mergeCatalogLoadState(
  previous: CatalogLoadState,
  hydrated: CatalogLoadState,
): CatalogLoadState {
  return {
    childrenLoaded: new Set([
      ...hydrated.childrenLoaded,
      ...previous.childrenLoaded,
    ]),
    tablesLoaded: new Set([...hydrated.tablesLoaded, ...previous.tablesLoaded]),
  };
}

/** True when a backend refresh replaced every database with an empty shell. */
export function shouldResetCatalogLoadOnRefresh(
  connection: Pick<BackendDataSourceConnection, "databases">,
): boolean {
  return connection.databases.every(
    (database) => database.children.length === 0,
  );
}

export function hydrateCatalogLoadState(
  connection: Pick<BackendDataSourceConnection, "databases">,
): CatalogLoadState {
  const childrenLoaded = new Set<string>();
  const tablesLoaded = new Set<string>();

  const visit = ({
    database,
    nodes,
    path,
  }: {
    database: string;
    nodes: CatalogNode[];
    path: string[];
  }): void => {
    if (nodes.length > 0) {
      markCatalogPathLoaded({
        childrenLoaded,
        tablesLoaded,
        database,
        path,
      });
    }

    for (const node of nodes) {
      if (isDataTableNode(node)) {
        tablesLoaded.add(catalogPathKey(database, path));
        continue;
      }

      if (isSchemaNode(node)) {
        const tablePath = catalogNodePath({
          schema: node.name,
          catalogPath: path,
        });
        if (node.tables.length > 0) {
          tablesLoaded.add(catalogPathKey(database, tablePath));
        }
        continue;
      }

      if (isNamespaceNode(node)) {
        const namespacePath = [...path, node.name];
        if (node.children.length > 0) {
          visit({
            database,
            nodes: node.children,
            path: namespacePath,
          });
        }
      }
    }
  };

  for (const database of connection.databases) {
    visit({
      database: database.name,
      nodes: database.children,
      path: [],
    });
  }

  return { childrenLoaded, tablesLoaded };
}
