/* Copyright 2024 Marimo. All rights reserved. */
import type { SQLTableContext } from "@/core/datasets/data-source-connections";
import { DUCKDB_ENGINE } from "@/core/datasets/engines";
import type { DataTable, DataType } from "@/core/kernel/messages";
import type { ColumnHeaderStatsKey } from "../data-table/types";

// Some databases have no schemas, so we don't show it (eg. Clickhouse)
export function isSchemaless(schemaName: string) {
  return schemaName === "";
}

interface SqlCodeFormatter {
  /**
   * Format the table name based on dialect-specific rules
   */
  formatTableName: (tableName: string) => string;
  /**
   * Format the SELECT clause
   */
  formatSelectClause: (columnName: string, tableName: string) => string;
}

const defaultFormatter: SqlCodeFormatter = {
  formatTableName: (tableName: string) => tableName,
  formatSelectClause: (columnName: string, tableName: string) =>
    `SELECT ${columnName} FROM ${tableName} LIMIT 100`,
};

const SQL_CODE_FORMATTERS: Record<string, SqlCodeFormatter> = {
  // BigQuery: Use backticks for identifiers
  bigquery: {
    formatTableName: (tableName: string) => `\`${tableName}\``,
    formatSelectClause: defaultFormatter.formatSelectClause,
  },
  // MSSQL: Use TOP instead of LIMIT
  mssql: {
    formatTableName: defaultFormatter.formatTableName,
    formatSelectClause: (columnName: string, tableName: string) =>
      `SELECT TOP 100 ${columnName} FROM ${tableName}`,
  },
  // TimescaleDB: Wrap each part of qualified name with double quotes
  timescaledb: {
    formatTableName: (tableName: string) => {
      const parts = tableName.split(".");
      return parts.map((part) => `"${part}"`).join(".");
    },
    formatSelectClause: defaultFormatter.formatSelectClause,
  },
  default: defaultFormatter,
};

export function sqlCode({
  table,
  columnName,
  sqlTableContext,
}: {
  table: DataTable;
  columnName: string;
  sqlTableContext?: SQLTableContext;
}) {
  if (sqlTableContext) {
    const {
      engine,
      schema,
      defaultSchema,
      defaultDatabase,
      database,
      dialect,
    } = sqlTableContext;
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

    const formatter =
      SQL_CODE_FORMATTERS[dialect.toLowerCase()] || defaultFormatter;
    const formattedTableName = formatter.formatTableName(tableName);
    const selectClause = formatter.formatSelectClause(
      columnName,
      formattedTableName,
    );

    if (engine === DUCKDB_ENGINE) {
      return `_df = mo.sql(f"""${selectClause}""")`;
    }

    return `_df = mo.sql(f"""${selectClause}""", engine=${engine})`;
  }

  return `_df = mo.sql(f'SELECT "${columnName}" FROM ${table.name} LIMIT 100')`;
}

export function convertStatsName(stat: ColumnHeaderStatsKey, type: DataType) {
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
