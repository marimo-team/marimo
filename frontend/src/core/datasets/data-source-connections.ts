/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { Logger } from "@/utils/Logger";
import type {
  DataSourceConnection as DataSourceConnectionType,
  DataTable,
} from "../kernel/messages";
import { store } from "../state/jotai";
import type { VariableName } from "../variables/types";
import {
  type CatalogNode,
  catalogNodePath,
  findNodeAtPath,
  isNamespaceNode,
  isSchemaNode,
  mergeTableAtPath,
  setCatalogChildrenAtPath,
  walkCatalogNodes,
} from "./catalog";
import {
  type ConnectionName,
  DUCKDB_ENGINE,
  INTERNAL_SQL_ENGINES,
} from "./engines";
import { datasetTablesAtom } from "./state";

const initialConnections: ConnectionsMap = new Map([
  [
    DUCKDB_ENGINE,
    {
      name: DUCKDB_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB (In-Memory)",
      databases: [],
    },
  ],
]);

// Extend the backend type but override the name property with the strongly typed ConnectionName
export type DataSourceConnection = Omit<DataSourceConnectionType, "name"> & {
  name: ConnectionName;
};

// Backwards-compatible alias; the backend connection is now the source of truth
// for catalog load state (deferred buckets are `null`).
export type DataSourceConnectionInput = DataSourceConnection;

export type ConnectionsMap = ReadonlyMap<ConnectionName, DataSourceConnection>;

export interface DataSourceState {
  latestEngineSelected: ConnectionName;
  connectionsMap: ConnectionsMap;
}

export interface SQLCatalogContext {
  engine: string;
  database: string;
  catalogPath?: string[];
}

export interface SQLTableContext {
  engine: string;
  database: string;
  schema: string;
  dialect: string;
  defaultSchema?: string | null;
  defaultDatabase?: string | null;
  // Nested namespace path (relative to `database`). Empty/undefined at top level.
  catalogPath?: string[];
}

function initialState(): DataSourceState {
  return {
    latestEngineSelected: DUCKDB_ENGINE,
    connectionsMap: initialConnections,
  };
}

const {
  reducer,
  createActions,
  valueAtom: dataSourceConnectionsAtom,
  useActions: useDataSourceActions,
} = createReducerAndAtoms(initialState, {
  addDataSourceConnection: (
    state: DataSourceState,
    opts: { connections: DataSourceConnectionInput[] },
  ): DataSourceState => {
    if (opts.connections.length === 0) {
      return state;
    }

    const { latestEngineSelected, connectionsMap } = state;

    // Update existing connections with latest values and add new ones.
    // The backend is the source of truth for the catalog tree: it deep-merges
    // lazily loaded subtrees across re-introspection, so we replace wholesale.
    const newMap = new Map(connectionsMap);
    for (const conn of opts.connections) {
      newMap.set(conn.name, conn);
    }

    return {
      latestEngineSelected,
      connectionsMap: newMap,
    };
  },

  // Keep internal engines and any connections that are used by variables
  filterDataSourcesFromVariables: (
    state: DataSourceState,
    variableNames: VariableName[],
  ) => {
    const { latestEngineSelected, connectionsMap } = state;
    const names = new Set(variableNames);
    const newMap = new Map(
      [...connectionsMap].filter(([name]) => {
        if (INTERNAL_SQL_ENGINES.has(name)) {
          return true;
        }
        return names.has(name as unknown as VariableName);
      }),
    );
    return {
      // If the latest engine selected is not in the new map, use the default engine
      latestEngineSelected: newMap.has(latestEngineSelected)
        ? latestEngineSelected
        : DUCKDB_ENGINE,
      connectionsMap: newMap,
    };
  },

  clearDataSourceConnections: (): DataSourceState => ({
    latestEngineSelected: DUCKDB_ENGINE,
    connectionsMap: new Map(),
  }),

  removeDataSourceConnection: (
    state: DataSourceState,
    connectionName: ConnectionName,
  ): DataSourceState => {
    const { latestEngineSelected, connectionsMap } = state;

    const newMap = new Map(connectionsMap);
    newMap.delete(connectionName);
    return {
      latestEngineSelected: newMap.has(latestEngineSelected)
        ? latestEngineSelected
        : DUCKDB_ENGINE,
      connectionsMap: newMap,
    };
  },

  // Add catalog children to a specific path in a connection
  addCatalogChildren: (
    state: DataSourceState,
    opts: {
      nodes: CatalogNode[];
      sqlCatalogContext: SQLCatalogContext;
    },
  ): DataSourceState => {
    const { nodes, sqlCatalogContext } = opts;
    const { connectionsMap, latestEngineSelected } = state;
    const connectionName = sqlCatalogContext.engine as ConnectionName;
    const databaseName = sqlCatalogContext.database;
    const catalogPath = sqlCatalogContext.catalogPath ?? [];
    const conn = connectionsMap.get(connectionName);

    if (!conn) {
      return state;
    }

    const database = conn.databases.find((db) => db.name === databaseName);
    if (!database) {
      return state;
    }

    if (catalogPath.length > 0) {
      const parentNode = findNodeAtPath({
        nodes: database.children ?? [],
        path: catalogPath,
      });
      if (
        parentNode === undefined ||
        (!isSchemaNode(parentNode) && !isNamespaceNode(parentNode))
      ) {
        return state;
      }
    }

    const newConn: DataSourceConnection = {
      ...conn,
      databases: conn.databases.map((db) =>
        db.name === databaseName
          ? {
              ...db,
              children: setCatalogChildrenAtPath({
                nodes: db.children ?? [],
                path: catalogPath,
                children: nodes,
              }),
            }
          : db,
      ),
    };
    const newMap = new Map(connectionsMap).set(connectionName, newConn);

    return {
      latestEngineSelected: latestEngineSelected,
      connectionsMap: newMap,
    };
  },

  // Add table to a specific connection
  addTable: (
    state: DataSourceState,
    opts: {
      table: DataTable;
      sqlTableContext: SQLTableContext;
    },
  ): DataSourceState => {
    const { table, sqlTableContext } = opts;
    const { connectionsMap, latestEngineSelected } = state;
    const connectionName = sqlTableContext.engine as ConnectionName;

    const conn = connectionsMap.get(connectionName);
    if (!conn) {
      return state;
    }

    const path = catalogNodePath({
      schema: sqlTableContext.schema,
      catalogPath: sqlTableContext.catalogPath,
    });
    const newMap = new Map(connectionsMap);
    const newConn: DataSourceConnection = {
      ...conn,
      databases: conn.databases.map((db) => {
        if (db.name !== sqlTableContext.database) {
          return db;
        }
        return {
          ...db,
          children: mergeTableAtPath({ nodes: db.children ?? [], path, table }),
        };
      }),
    };
    newMap.set(connectionName, newConn);

    return {
      latestEngineSelected: latestEngineSelected,
      connectionsMap: newMap,
    };
  },
});

export { dataSourceConnectionsAtom, useDataSourceActions };

export const dataConnectionsMapAtom = atom(
  (get) => get(dataSourceConnectionsAtom).connectionsMap,
);

export function setLatestEngineSelected(engine: ConnectionName) {
  const existing = store.get(dataSourceConnectionsAtom);
  // Don't update the map if the engine is not in the map
  if (existing.connectionsMap.has(engine)) {
    store.set(dataSourceConnectionsAtom, {
      ...existing,
      latestEngineSelected: engine,
    });
  }
}

export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
};

/**
 * If you need to get table names from all connections & local datasets, use this atom.
 * Uses a more qualified name if there are collisions.
 */
export const allTablesAtom = atom((get) => {
  const datasets = store.get(datasetTablesAtom);
  const connections = get(dataSourceConnectionsAtom).connectionsMap;
  const tableNames = new Map<string, DataTable>();

  for (const dataset of datasets) {
    tableNames.set(dataset.name, dataset);
  }

  for (const conn of connections.values()) {
    for (const database of conn.databases) {
      // If there is only one database, it is the default
      const isDefaultDb =
        database.name === conn.default_database || conn.databases.length === 1;

      walkCatalogNodes({
        nodes: database.children ?? [],
        context: { databaseName: database.name, segments: [] },
        visit: ({ node, segments }) => {
          if (isNamespaceNode(node)) {
            return;
          }

          const rootLevelTable = segments.length === 0;
          const isDefaultSchema =
            segments.length === 1 && segments[0] === conn.default_schema;
          const schemaQualifier = segments.join(".");

          const tables = isSchemaNode(node) ? (node.tables ?? []) : [node];

          for (const table of tables) {
            let nameToSave: string = table.name;

            if (rootLevelTable) {
              nameToSave = isDefaultDb
                ? table.name
                : `${database.name}.${table.name}`;

              if (tableNames.has(nameToSave)) {
                Logger.warn(
                  `Table name collision for ${nameToSave}. Skipping.`,
                );
              } else {
                tableNames.set(nameToSave, table);
              }
              continue;
            }

            if (isDefaultDb && isDefaultSchema && !tableNames.has(nameToSave)) {
              tableNames.set(nameToSave, table);
              continue;
            }

            nameToSave = `${schemaQualifier}.${table.name}`;

            if (isDefaultDb && !tableNames.has(nameToSave)) {
              tableNames.set(nameToSave, table);
              continue;
            }

            nameToSave = `${database.name}.${schemaQualifier}.${table.name}`;

            if (tableNames.has(nameToSave)) {
              Logger.warn(`Table name collision for ${nameToSave}. Skipping.`);
            } else {
              tableNames.set(nameToSave, table);
            }
          }
        },
      });
    }
  }

  return tableNames;
});

/**
 * Dataframes are tables that are created from local Python dataframes
 * In-memory engines can access dataframes
 */
export function getTableType(table: DataTable): "table" | "dataframe" {
  return table.variable_name ? "dataframe" : "table";
}

export type DatasetTablesMap = ReturnType<(typeof allTablesAtom)["read"]>;
