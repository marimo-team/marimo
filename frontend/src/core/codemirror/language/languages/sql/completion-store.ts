/* Copyright 2026 Marimo. All rights reserved. */

import type { SQLConfig, SQLDialect } from "@codemirror/lang-sql";
import { atom } from "jotai";
import { isSchemaless } from "@/components/datasources/utils";
import { dataConnectionsMapAtom } from "@/core/datasets/data-source-connections";
import type { ConnectionName } from "@/core/datasets/engines";
import { datasetTablesAtom } from "@/core/datasets/state";
import type { DataSourceConnection } from "@/core/kernel/messages";
import { store } from "@/core/state/jotai";
import { LRUCache } from "@/utils/lru";
import { CompletionBuilder } from "./completion-builder";
import { guessDialect, ModifiedStandardSQL } from "./utils";

type CachedSchema = Pick<SQLConfig, "schema" | "defaultSchema"> & {
  shouldAddLocalTables: boolean;
};

const datasetTableCompletionsAtom = atom((get) => {
  const tables = get(datasetTablesAtom);
  const builder = new CompletionBuilder();
  for (const table of tables) {
    builder.addTable([], table);
  }
  return builder.build();
});

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
    const { default_database, databases, default_schema } = connection;
    const builder = new CompletionBuilder();

    // When there is only one database, it is the default
    const defaultDb = databases.find(
      (db) => db.name === default_database || databases.length === 1,
    );

    const dbToVerify = defaultDb ?? databases[0];
    const isSchemalessDb =
      dbToVerify?.schemas.some((schema) => isSchemaless(schema.name)) ?? false;

    // For schemaless databases, treat databases as schemas
    if (isSchemalessDb) {
      for (const db of databases) {
        const isDefaultDb = db.name === defaultDb?.name;
        const tables = db.schemas.flatMap((schema) => schema.tables);
        builder.addDatabase([db.name], db);

        for (const table of tables) {
          if (isDefaultDb) {
            // For default database, add tables directly to top level
            builder.addTable([], table);
          } else {
            // Otherwise nest under database name
            builder.addTable([db.name], table);
          }
        }
      }

      return {
        shouldAddLocalTables: false,
        schema: builder.build(),
        defaultSchema: defaultDb?.name,
      };
    }

    // For default db, we can use the schema name directly so add them to the top level
    if (defaultDb) {
      for (const schema of defaultDb.schemas) {
        builder.addSchema([schema.name], schema);

        for (const table of schema.tables) {
          builder.addTable([schema.name], table);
        }
      }
    }

    // Otherwise, we need to use the fully qualified name
    for (const database of databases) {
      // We still want to add the default database here in case
      // users want fully qualified names for completions

      builder.addDatabase([database.name], database);

      for (const schema of database.schemas) {
        builder.addSchema([database.name, schema.name], schema);

        for (const table of schema.tables) {
          builder.addTable([database.name, schema.name], table);
        }
      }
    }

    return {
      shouldAddLocalTables: true,
      schema: builder.build(),
      defaultSchema: default_schema ?? undefined,
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
    return connection.dialect.toLowerCase();
  }

  /**
   * Get the inferred SQL dialect for a connection
   * If the connection is not found, return the standard SQL dialect.
   */
  getDialect(connectionName: ConnectionName): SQLDialect {
    const connection = this.getConnection(connectionName);
    if (!connection) {
      return ModifiedStandardSQL;
    }
    return guessDialect(connection);
  }

  getCompletionSource(connectionName: ConnectionName): SQLConfig | null {
    const connection = this.getConnection(connectionName);
    if (!connection) {
      return null;
    }

    const getTablesMap = () => {
      // If there is a conflict with connection tables,
      // the engine will prioritize the connection tables without special handling
      return store.get(datasetTableCompletionsAtom);
    };

    const schema = this.cache.getOrCreate(connection);

    return {
      dialect: guessDialect(connection),
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
