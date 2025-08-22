/* Copyright 2024 Marimo. All rights reserved. */

import {
  type SQLConfig,
  type SQLDialect,
  StandardSQL,
} from "@codemirror/lang-sql";
import { isSchemaless } from "@/components/datasources/utils";
import { dataConnectionsMapAtom } from "@/core/datasets/data-source-connections";
import type { ConnectionName } from "@/core/datasets/engines";
import { datasetTablesAtom } from "@/core/datasets/state";
import type { DataSourceConnection } from "@/core/kernel/messages";
import { store } from "@/core/state/jotai";
import { LRUCache } from "@/utils/lru";
import { guessDialect, ModifiedStandardSQL } from "./utils";

type TableToCols = Record<string, string[]>;
type Schemas = Record<string, TableToCols>;
type CachedSchema = Pick<SQLConfig, "schema" | "defaultSchema"> & {
  shouldAddLocalTables: boolean;
};

class SQLCompletionStore {
  private cache: LRUCache<DataSourceConnection, CachedSchema>;

  constructor() {
    this.cache = new LRUCache(10, {
      create: (connection) => this.getConnectionSchema(connection),
    });
  }

  private getConnection(
    connectionName: ConnectionName,
  ): DataSourceConnection | undefined {
    const dataConnectionsMap = store.get(dataConnectionsMapAtom);
    return dataConnectionsMap.get(connectionName);
  }

  private getConnectionSchema(connection: DataSourceConnection): CachedSchema {
    const schemaMap: Record<string, TableToCols> = {};
    const databaseMap: Record<string, Schemas> = {};

    // When there is only one database, it is the default
    const defaultDb = connection.databases.find(
      (db) =>
        db.name === connection.default_database ||
        connection.databases.length === 1,
    );

    const dbToVerify = defaultDb ?? connection.databases[0];
    const isSchemalessDb =
      dbToVerify?.schemas.some((schema) => isSchemaless(schema.name)) ?? false;

    // For schemaless databases, treat databases as schemas
    if (isSchemalessDb) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const dbToTablesMap: Record<string, any> = {};

      for (const db of connection.databases) {
        const isDefaultDb = db.name === defaultDb?.name;

        for (const schema of db.schemas) {
          for (const table of schema.tables) {
            const columns = table.columns.map((col) => col.name);

            if (isDefaultDb) {
              // For default database, add tables directly to top level
              dbToTablesMap[table.name] = columns;
            } else {
              // Otherwise nest under database name
              dbToTablesMap[db.name] = dbToTablesMap[db.name] || {};
              dbToTablesMap[db.name][table.name] = columns;
            }
          }
        }
      }

      return {
        shouldAddLocalTables: false,
        schema: dbToTablesMap,
        defaultSchema: defaultDb?.name,
      };
    }

    // For default db, we can use the schema name directly
    for (const schema of defaultDb?.schemas ?? []) {
      schemaMap[schema.name] = {};
      for (const table of schema.tables) {
        const columns = table.columns.map((col) => col.name);
        schemaMap[schema.name][table.name] = columns;
      }
    }

    // Otherwise, we need to use the fully qualified name
    for (const database of connection.databases) {
      if (database.name === defaultDb?.name) {
        continue;
      }
      databaseMap[database.name] = {};

      for (const schema of database.schemas) {
        databaseMap[database.name][schema.name] = {};

        for (const table of schema.tables) {
          const columns = table.columns.map((col) => col.name);
          databaseMap[database.name][schema.name][table.name] = columns;
        }
      }
    }

    return {
      shouldAddLocalTables: true,
      schema: { ...databaseMap, ...schemaMap },
      defaultSchema: connection.default_schema ?? undefined,
    };
  }

  /**
   * Returns the raw dialect of the connection passed from the backend,
   * or null if the connection is not found
   */
  getInternalDialect(connectionName: ConnectionName): string | null {
    const connection = this.getConnection(connectionName);
    if (!connection) {
      return null;
    }
    return connection.dialect;
  }

  /**
   * Get the inferred SQL dialect for a connection
   * If the connection is not found, return the standard SQL dialect.
   */
  getDialect(connectionName: ConnectionName): SQLDialect {
    const connection = this.getConnection(connectionName);
    if (!connection) {
      return StandardSQL;
    }
    return guessDialect(connection) ?? ModifiedStandardSQL;
  }

  getCompletionSource(connectionName: ConnectionName): SQLConfig | null {
    const connection = this.getConnection(connectionName);
    if (!connection) {
      return null;
    }

    const getTablesMap = () => {
      const localTables = store.get(datasetTablesAtom);
      // If there is a conflict with connection tables,
      // the engine will prioritize the connection tables without special handling
      const tablesMap: TableToCols = {};
      for (const table of localTables) {
        const tableColumns = table.columns.map((col) => col.name);
        tablesMap[table.name] = tableColumns;
      }
      return tablesMap;
    };

    const schema = this.cache.getOrCreate(connection);

    return {
      dialect: guessDialect(connection) ?? ModifiedStandardSQL,
      schema: schema.shouldAddLocalTables
        ? { ...schema.schema, ...getTablesMap() }
        : schema.schema,
      defaultSchema: schema.defaultSchema,
      defaultTable: getSingleTable(connection),
    };
  }
}

function getSingleTable(connection: DataSourceConnection): string | undefined {
  if (connection.databases.length !== 1) {
    return undefined;
  }
  const database = connection.databases[0];
  if (database.schemas.length !== 1) {
    return undefined;
  }
  const schema = database.schemas[0];
  if (schema.tables.length !== 1) {
    return undefined;
  }
  return schema.tables[0].name;
}

export const SCHEMA_CACHE = new SQLCompletionStore();

// For testing
export { SQLCompletionStore as TestSQLCompletionStore };
