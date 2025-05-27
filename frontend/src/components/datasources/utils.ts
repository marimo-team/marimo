/* Copyright 2024 Marimo. All rights reserved. */
import {
  type SQLTableContext,
  DUCKDB_ENGINE,
} from "@/core/datasets/data-source-connections";
import type { DataTable, DataType } from "@/core/kernel/messages";
import type { ColumnHeaderStatsKeys } from "../data-table/types";

// Some databases have no schemas, so we don't show it (eg. Clickhouse)
export function isSchemaless(schemaName: string) {
  return schemaName === "";
}

export function sqlCode(
  table: DataTable,
  columnName: string,
  sqlTableContext?: SQLTableContext,
) {
  if (sqlTableContext) {
    const { engine, schema, defaultSchema, defaultDatabase, database } =
      sqlTableContext;
    let tableName = table.name;

    // Set the fully qualified table name based on schema and database
    if (isSchemaless(schema)) {
      tableName =
        database === defaultDatabase ? tableName : `${database}.${tableName}`;
    } else {
      // Include schema if it's not the default schema
      if (schema !== defaultSchema) {
        tableName = `${schema}.${tableName}`;
      }

      // Include database if it's not the default database
      if (database !== defaultDatabase) {
        tableName = `${database}.${tableName}`;
      }
    }

    if (engine === DUCKDB_ENGINE) {
      return `_df = mo.sql(f"SELECT ${columnName} FROM ${tableName} LIMIT 100")`;
    }

    return `_df = mo.sql(f"SELECT ${columnName} FROM ${tableName} LIMIT 100", engine=${engine})`;
  }

  return `_df = mo.sql(f'SELECT "${columnName}" FROM ${table.name} LIMIT 100')`;
}

export function convertStatsName(
  stat: (typeof ColumnHeaderStatsKeys)[number],
  type: DataType,
) {
  if (type === "date" || type === "datetime" || type === "time") {
    if (stat === "min") {
      return "Earliest";
    }
    if (stat === "max") {
      return "Latest";
    }
  }
  return stat;
}
