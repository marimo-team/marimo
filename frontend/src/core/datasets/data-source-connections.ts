/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import { isSchemaless } from "@/components/datasources/utils";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { Logger } from "@/utils/Logger";
import type {
  DatabaseSchema,
  DataSourceConnection as DataSourceConnectionType,
  DataTable,
} from "../kernel/messages";
import { store } from "../state/jotai";
import type { VariableName } from "../variables/types";
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
export interface DataSourceConnection extends Omit<
  DataSourceConnectionType,
  "name"
> {
  name: ConnectionName;
}

export type ConnectionsMap = ReadonlyMap<ConnectionName, DataSourceConnection>;

export interface DataSourceState {
  latestEngineSelected: ConnectionName;
  connectionsMap: ConnectionsMap;
}

export interface SQLSchemaContext {
  engine: string;
  database: string;
  // Parent schema path (relative to `database`) for nested schemas.
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
  // Nested schema path (relative to `database`). Empty/undefined at top level.
  schemaPath?: string[];
}

/**
 * Immutably descend `path` (schema segment names) into a nested schema list
 * and apply `update` to the matching schema. Unmatched branches are unchanged.
 */
function updateSchemaAtPath(
  schemas: DatabaseSchema[],
  path: string[],
  update: (schema: DatabaseSchema) => DatabaseSchema,
): DatabaseSchema[] {
  if (path.length === 0) {
    return schemas;
  }
  const [head, ...rest] = path;
  return schemas.map((schema) => {
    if (schema.name !== head) {
      return schema;
    }
    if (rest.length === 0) {
      return update(schema);
    }
    return {
      ...schema,
      schemas: updateSchemaAtPath(schema.schemas ?? [], rest, update),
    };
  });
}

/**
 * The path (schema/namespace segment names within a database) that locates the
 * schema holding a set of tables. For nested namespaces this is the
 * `schemaPath`; otherwise it is the single (possibly schemaless) schema name.
 */
function tableSchemaPath(sqlTableContext: SQLTableContext): string[] {
  const { schemaPath, schema } = sqlTableContext;
  return schemaPath && schemaPath.length > 0 ? schemaPath : [schema];
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

  // Add schema list to a specific database in a connection
  addSchemaList: (
    state: DataSourceState,
    opts: {
      schemas: DatabaseSchema[];
      sqlSchemaContext: SQLSchemaContext;
    },
  ): DataSourceState => {
    const { schemas, sqlSchemaContext } = opts;
    const { connectionsMap, latestEngineSelected } = state;
    const connectionName = sqlSchemaContext.engine as ConnectionName;
    const conn = connectionsMap.get(connectionName);

    if (!conn) {
      return state;
    }

    const schemaPath = sqlSchemaContext.schemaPath ?? [];
    const newMap = new Map(connectionsMap);
    const newConn: DataSourceConnection = {
      ...conn,
      databases: conn.databases.map((db) => {
        if (db.name !== sqlSchemaContext.database) {
          return db;
        }
        // Top level: replace the database's schemas.
        if (schemaPath.length === 0) {
          return {
            ...db,
            schemas: schemas,
            schemas_resolved: true,
          };
        }
        // Nested namespace: replace the child schemas of the namespace at path.
        return {
          ...db,
          schemas: updateSchemaAtPath(db.schemas, schemaPath, (schema) => ({
            ...schema,
            schemas: schemas,
            schemas_resolved: true,
          })),
        };
      }),
    };
    newMap.set(connectionName, newConn);

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

    const path = tableSchemaPath(sqlTableContext);
    const newMap = new Map(connectionsMap);
    const newConn: DataSourceConnection = {
      ...conn,
      databases: conn.databases.map((db) => {
        if (db.name !== sqlTableContext.database) {
          return db;
        }
        return {
          ...db,
          schemas: updateSchemaAtPath(db.schemas, path, (schema) => ({
            ...schema,
            tables: tables,
            tables_resolved: true,
          })),
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

    const path = tableSchemaPath(sqlTableContext);
    const newMap = new Map(connectionsMap);
    const newConn: DataSourceConnection = {
      ...conn,
      databases: conn.databases.map((db) => {
        if (db.name !== sqlTableContext.database) {
          return db;
        }
        return {
          ...db,
          schemas: updateSchemaAtPath(db.schemas, path, (schema) => {
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

      // Walk schemas recursively so nested namespaces (e.g. Iceberg
      // `top.nested`) are enumerated. `segments` is the path of named
      // (non-schemaless) namespace segments down to this schema.
      const walkSchema = (schema: DatabaseSchema, segments: string[]): void => {
        const schemalessDb = segments.length === 0;
        const isDefaultSchema =
          segments.length === 1 && segments[0] === conn.default_schema;
        const schemaQualifier = segments.join(".");

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

        // Recurse into nested child namespaces. Children are always named.
        for (const child of schema.schemas ?? []) {
          walkSchema(child, [...segments, child.name]);
        }
      };

      for (const schema of database.schemas) {
        walkSchema(schema, isSchemaless(schema.name) ? [] : [schema.name]);
      }
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
