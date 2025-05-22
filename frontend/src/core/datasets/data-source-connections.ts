/* Copyright 2024 Marimo. All rights reserved. */
import { createReducerAndAtoms } from "@/utils/createReducer";
import type {
  DataSourceConnection as DataSourceConnectionType,
  DataTable,
} from "../kernel/messages";
import type { TypedString } from "@/utils/typed";
import type { VariableName } from "../variables/types";
import { atom } from "jotai";
import { store } from "../state/jotai";
import { datasetTablesAtom } from "./state";
import { Logger } from "@/utils/Logger";
import { isSchemaless } from "@/components/datasources/utils";

export type ConnectionName = TypedString<"ConnectionName">;

// DuckDB engine is treated as the default engine
// As it doesn't require passing an engine variable to the backend
// Keep this in sync with the backend name
export const DUCKDB_ENGINE = "__marimo_duckdb" as ConnectionName;
export const INTERNAL_SQL_ENGINES = new Set([DUCKDB_ENGINE]);

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
export interface DataSourceConnection
  extends Omit<DataSourceConnectionType, "name"> {
  name: ConnectionName;
}

type ConnectionsMap = ReadonlyMap<ConnectionName, DataSourceConnection>;

export interface DataSourceState {
  latestEngineSelected: ConnectionName;
  connectionsMap: ConnectionsMap;
}

export interface SQLTableContext {
  engine: string;
  database: string;
  schema: string;
  defaultSchema?: string | null;
  defaultDatabase?: string | null;
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
    opts: { connections: DataSourceConnection[] },
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

    const newMap = new Map(connectionsMap);
    const newConn: DataSourceConnection = {
      ...conn,
      databases: conn.databases.map((db) => {
        if (db.name !== sqlTableContext.database) {
          return db;
        }
        return {
          ...db,
          schemas: db.schemas.map((schema) => {
            if (schema.name !== sqlTableContext.schema) {
              return schema;
            }
            return {
              ...schema,
              tables: tables,
            };
          }),
        };
      }),
    };
    newMap.set(connectionName, newConn);

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
    const tableName = table.name;

    const conn = connectionsMap.get(connectionName);
    if (!conn) {
      return state;
    }

    const newMap = new Map(connectionsMap);
    const newConn: DataSourceConnection = {
      ...conn,
      databases: conn.databases.map((db) => {
        if (db.name !== sqlTableContext.database) {
          return db;
        }

        return {
          ...db,
          schemas: db.schemas.map((schema) => {
            if (schema.name !== sqlTableContext.schema) {
              return schema;
            }

            // If tables array is empty, add the table
            // Otherwise, replace existing table or keep unchanged tables
            const tables =
              schema.tables.length === 0
                ? [table]
                : schema.tables.map((t) => (t.name === tableName ? table : t));

            return {
              ...schema,
              tables,
            };
          }),
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

      for (const schema of database.schemas) {
        const isDefaultSchema = schema.name === conn.default_schema;
        const schemalessDb = isSchemaless(schema.name);

        for (const table of schema.tables) {
          let nameToSave: string;

          // If the database and schema are default, we can use the table name directly
          // Otherwise, we need to qualify the table name
          // We also need to use the more qualified name if there are collisions
          nameToSave = table.name;

          // Save either dbName.table / tableName
          if (schemalessDb) {
            nameToSave = isDefaultDb
              ? table.name
              : `${database.name}.${table.name}`;

            if (tableNames.has(nameToSave)) {
              Logger.warn(`Table name collision for ${nameToSave}. Skipping.`);
            } else {
              tableNames.set(nameToSave, table);
            }
            continue;
          }

          if (isDefaultDb && isDefaultSchema && !tableNames.has(nameToSave)) {
            tableNames.set(nameToSave, table);
            continue;
          }

          nameToSave = `${schema.name}.${table.name}`;

          if (isDefaultDb && !tableNames.has(nameToSave)) {
            tableNames.set(nameToSave, table);
            continue;
          }

          nameToSave = `${database.name}.${schema.name}.${table.name}`;

          if (tableNames.has(nameToSave)) {
            Logger.warn(`Table name collision for ${nameToSave}. Skipping.`);
          } else {
            tableNames.set(nameToSave, table);
          }
        }
      }
    }
  }

  return tableNames;
});

export type DatasetTablesMap = ReturnType<(typeof allTablesAtom)["read"]>;
