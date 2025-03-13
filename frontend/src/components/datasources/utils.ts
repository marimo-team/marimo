/* Copyright 2024 Marimo. All rights reserved. */
import {
  type SQLTableContext,
  DEFAULT_ENGINE,
} from "@/core/datasets/data-source-connections";
import type { DataTable } from "@/core/kernel/messages";

export function sqlCode(
  table: DataTable,
  columnName: string,
  sqlTableContext?: SQLTableContext,
) {
  if (sqlTableContext) {
    const { engine, schema, defaultSchema, defaultDatabase, database } =
      sqlTableContext;
    let tableName = table.name;

    // If the schema is not the default schema, we need to include the schema in the table name
    if (schema !== defaultSchema) {
      tableName = `${schema}.${tableName}`;
    }
    // If the database is not the default database, we need to include the database in the table name
    if (database !== defaultDatabase) {
      tableName = `${database}.${tableName}`;
    }

    if (engine === DEFAULT_ENGINE) {
      return `_df = mo.sql(f"SELECT ${columnName} FROM ${tableName} LIMIT 100")`;
    }

    return `_df = mo.sql(f"SELECT ${columnName} FROM ${tableName} LIMIT 100", engine=${engine})`;
  }

  return `_df = mo.sql(f'SELECT "${columnName}" FROM ${table.name} LIMIT 100')`;
}
