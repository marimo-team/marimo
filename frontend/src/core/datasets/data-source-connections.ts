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
  setChildNodesAtPath,
  setTablesAtPath,
  walkCatalogNodes,
} from "./catalog";
import {
  type CatalogLoadState,
  catalogPathKey,
  emptyCatalogLoadState,
  hydrateCatalogLoadState,
} from "./catalog-load-state";
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
      catalogLoad: emptyCatalogLoadState(),
    },
  ],
]);

// Extend the backend type but override the name property with the strongly typed ConnectionName
export type DataSourceConnectionInput = Omit<
  DataSourceConnectionType,
  "name"
> & {
  name: ConnectionName;
};

export interface DataSourceConnection extends DataSourceConnectionInput {
  catalogLoad: CatalogLoadState;
}

export type ConnectionsMap = ReadonlyMap<ConnectionName, DataSourceConnection>;

export interface DataSourceState {
  latestEngineSelected: ConnectionName;
  connectionsMap: ConnectionsMap;
}

export interface SQLSchemaContext {
  engine: string;
  database: string;
  // Parent namespace path (relative to `database`) for nested catalogs.
  // Empty/undefined for the database's top level.
  schemaPath?: string[];
}

export interface SQLTableContext {
  engine: string;
  database: string;
  schema: string;
  dialect: string;
  defaultSchema?: string | null;
  defaultDatabase?: string | null;
  // Nested namespace path (relative to `database`). Empty/undefined at top level.
  schemaPath?: string[];
}

function initialState(): DataSourceState {
  return {
    latestEngineSelected: DUCKDB_ENGINE,
    connectionsMap: initialConnections,
  };
}

function mergeCatalogLoadState(
  existing: CatalogLoadState,
  incoming: CatalogLoadState,
): CatalogLoadState {
  return {
    childrenLoaded: new Set([
      ...existing.childrenLoaded,
      ...incoming.childrenLoaded,
    ]),
    tablesLoaded: new Set([...existing.tablesLoaded, ...incoming.tablesLoaded]),
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

    // update existing connections with latest values
    // add new ones if they don't exist
    // Backend will dedupe by connection name & keep the latest, so we use this as the key
    const newMap = new Map(connectionsMap);
    for (const conn of opts.connections) {
      const existing = newMap.get(conn.name);
      newMap.set(conn.name, {
        ...conn,
        catalogLoad: mergeCatalogLoadState(
          existing?.catalogLoad ?? emptyCatalogLoadState(),
          hydrateCatalogLoadState(conn),
        ),
      });
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

  // Add schema list to a specific database in a connection
  addSchemaList: (
    state: DataSourceState,
    opts: {
      nodes: CatalogNode[];
      sqlSchemaContext: SQLSchemaContext;
    },
  ): DataSourceState => {
    const { nodes, sqlSchemaContext } = opts;
    const { connectionsMap, latestEngineSelected } = state;
    const connectionName = sqlSchemaContext.engine as ConnectionName;
    const databaseName = sqlSchemaContext.database;
    const schemaPath = sqlSchemaContext.schemaPath ?? [];
    const conn = connectionsMap.get(connectionName);

    if (!conn) {
      return state;
    }

    const database = conn.databases.find((db) => db.name === databaseName);
    if (!database) {
      return state;
    }

    const parentNode = findNodeAtPath({
      nodes: database.children,
      path: schemaPath,
    });
    if (
      schemaPath.length > 0 &&
      (parentNode === undefined || !isNamespaceNode(parentNode))
    ) {
      return state;
    }

    const childrenLoadKey = catalogPathKey(databaseName, schemaPath);
    const newConn: DataSourceConnection = {
      ...conn,
      catalogLoad: {
        ...conn.catalogLoad,
        childrenLoaded: new Set([
          ...conn.catalogLoad.childrenLoaded,
          childrenLoadKey,
        ]),
      },
      databases: conn.databases.map((db) =>
        db.name === databaseName
          ? {
              ...db,
              children: setChildNodesAtPath({
                nodes: db.children,
                path: schemaPath,
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

  // Add table list to a specific schema in a connection
  addTableList: (
    state: DataSourceState,
    opts: {
      tables: DataTable[];
      sqlTableContext: SQLTableContext;
    },
  ): DataSourceState => {
    const { tables, sqlTableContext } = opts;
    const { connectionsMap, latestEngineSelected } = state;
    const connectionName = sqlTableContext.engine as ConnectionName;
    const conn = connectionsMap.get(connectionName);

    if (!conn) {
      return state;
    }

    const path = catalogNodePath({
      schema: sqlTableContext.schema,
      schemaPath: sqlTableContext.schemaPath,
    });
    const databaseName = sqlTableContext.database;
    const database = conn.databases.find((db) => db.name === databaseName);
    if (!database) {
      return state;
    }

    const targetNode = findNodeAtPath({ nodes: database.children, path });
    if (
      targetNode === undefined ||
      (!isSchemaNode(targetNode) && !isNamespaceNode(targetNode))
    ) {
      return state;
    }

    const tablesLoadKey = catalogPathKey(sqlTableContext.database, path);
    const newConn: DataSourceConnection = {
      ...conn,
      catalogLoad: {
        ...conn.catalogLoad,
        tablesLoaded: new Set([
          ...conn.catalogLoad.tablesLoaded,
          tablesLoadKey,
        ]),
      },
      databases: conn.databases.map((db) =>
        db.name === databaseName
          ? {
              ...db,
              children: setTablesAtPath({ nodes: db.children, path, tables }),
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
      schemaPath: sqlTableContext.schemaPath,
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
          children: mergeTableAtPath({ nodes: db.children, path, table }),
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
        nodes: database.children,
        context: { databaseName: database.name, segments: [] },
        visit: ({ node, segments }) => {
          if (isNamespaceNode(node)) {
            return;
          }

          const schemalessDb = segments.length === 0;
          const isDefaultSchema =
            segments.length === 1 && segments[0] === conn.default_schema;
          const schemaQualifier = segments.join(".");

          const tables = isSchemaNode(node) ? node.tables : [node];

          for (const table of tables) {
            let nameToSave: string = table.name;

            if (schemalessDb) {
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
