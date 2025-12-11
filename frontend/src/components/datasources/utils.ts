/* Copyright 2024 Marimo. All rights reserved. */

import { BigQueryDialect } from "@marimo-team/codemirror-sql/dialects";
import { isKnownDialect } from "@/core/codemirror/language/languages/sql/utils";
import type { SQLTableContext } from "@/core/datasets/data-source-connections";
import { DUCKDB_ENGINE } from "@/core/datasets/engines";
import type { DataTable, DataType } from "@/core/kernel/messages";
import { logNever } from "@/utils/assertNever";
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

function getFormatter(dialect: string): SqlCodeFormatter {
  dialect = dialect.toLowerCase();
  if (!isKnownDialect(dialect)) {
    return defaultFormatter;
  }

  switch (dialect) {
    case "bigquery": {
      const quote = BigQueryDialect.spec.identifierQuotes;
      return {
        // BigQuery uses backticks for identifiers
        formatTableName: (tableName: string) => `${quote}${tableName}${quote}`,
        formatSelectClause: defaultFormatter.formatSelectClause,
      };
    }
    case "mssql":
    case "sqlserver":
      return {
        formatTableName: defaultFormatter.formatTableName,
        formatSelectClause: (columnName: string, tableName: string) =>
          `SELECT TOP 100 ${columnName} FROM ${tableName}`,
      };
    case "timescaledb":
    case "postgres":
    case "postgresql":
    case "duckdb":
      // Quote column and table names to avoid raising errors on weird characters
      return {
        formatTableName: (tableName: string) => {
          const parts = tableName.split(".");
          return parts.map((part) => `"${part}"`).join(".");
        },
        formatSelectClause: (columnName: string, tableName: string) =>
          `SELECT ${columnName === "*" ? "*" : `"${columnName}"`} FROM ${tableName} LIMIT 100`,
      };
    case "db2":
    case "db2i":
    case "mysql":
    case "sqlite":
    case "mariadb":
    case "cassandra":
    case "noql":
    case "awsathena":
    case "athena":
    case "hive":
    case "redshift":
    case "snowflake":
    case "flink":
    case "mongodb":
    case "oracle":
    case "oracledb":
    case "couchbase":
    case "tidb":
    case "spark":
    case "trino":
    case "singlestoredb":
      return defaultFormatter;
    default:
      logNever(dialect);
      return defaultFormatter;
  }
}

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

    const formatter = getFormatter(dialect);
    const formattedTableName = formatter.formatTableName(tableName);
    const selectClause = formatter.formatSelectClause(
      columnName,
      formattedTableName,
    );

    if (engine === DUCKDB_ENGINE) {
      return `_df = mo.sql(f"""\n${selectClause}\n""")`;
    }

    return `_df = mo.sql(f"""\n${selectClause}\n""", engine=${engine})`;
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
