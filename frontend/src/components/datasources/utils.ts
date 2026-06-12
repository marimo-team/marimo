/* Copyright 2026 Marimo. All rights reserved. */

import { BigQueryDialect } from "@marimo-team/codemirror-sql/dialects";
import { isKnownDialect } from "@/core/codemirror/language/languages/sql/utils";
import { catalogNodePath } from "@/core/datasets/catalog";
import type { SQLTableContext } from "@/core/datasets/data-source-connections";
import { DUCKDB_ENGINE } from "@/core/datasets/engines";
import type {
  Database,
  DatabaseNamespace,
  DatabaseSchema,
  DataTable,
  DataType,
} from "@/core/kernel/messages";
import { logNever } from "@/utils/assertNever";
import type { ColumnHeaderStatsKey } from "../data-table/types";

/**
 * Stable id for a table node in the datasources tree.
 *
 * schemaPath already includes the leaf schema for nested namespaces, so use it
 * when present and fall back to the flat schema name otherwise (avoids
 * duplicating the leaf, e.g. `top.nested.nested.table`).
 */
export function tableUniqueId(
  sqlTableContext: SQLTableContext | undefined,
  tableName: string,
): string {
  if (!sqlTableContext) {
    return tableName;
  }
  const segments = catalogNodePath(
    sqlTableContext.schema,
    sqlTableContext.schemaPath,
  ).filter(Boolean);
  return [sqlTableContext.database, ...segments, tableName].join(".");
}

// Some databases have no schemas, so we don't show it (eg. Clickhouse)
export function isSchemaless(schemaName: string) {
  return schemaName === "";
}

// Lazy discovery: the `*_resolved` flags default to `true` and are only `false`
// when enumeration was deferred. Helper functions to centralize logic
export function areChildrenResolved(database: Database): boolean {
  return database.children_resolved !== false;
}
export function areTablesResolved(schema: DatabaseSchema): boolean {
  return schema.tables_resolved !== false;
}
export function areNamespaceChildrenResolved(
  namespace: DatabaseNamespace,
): boolean {
  return namespace.children_resolved !== false;
}
export function areNamespaceTablesResolved(
  namespace: DatabaseNamespace,
): boolean {
  return namespace.tables_resolved !== false;
}

interface SqlCodeFormatter {
  /**
   * Format the table path based on dialect-specific rules
   */
  formatTablePath: (tablePath: string[]) => string;
  /**
   * Format the SELECT clause
   */
  formatSelectClause: (columnName: string, tableName: string) => string;
}

const defaultFormatter: SqlCodeFormatter = {
  formatTablePath: (tablePath: string[]) => tablePath.join("."),
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
        formatTablePath: (tablePath: string[]) =>
          `${quote}${tablePath.join(".")}${quote}`,
        formatSelectClause: defaultFormatter.formatSelectClause,
      };
    }
    case "mssql":
    case "sqlserver":
    case "microsoft sql server":
      return {
        formatTablePath: defaultFormatter.formatTablePath,
        formatSelectClause: (columnName: string, tableName: string) =>
          `SELECT TOP 100 ${columnName} FROM ${tableName}`,
      };
    case "timescaledb":
    case "postgres":
    case "postgresql":
    case "duckdb":
    case "dremio":
      // Quote column and table names to avoid raising errors on weird characters
      return {
        formatTablePath: (tablePath: string[]) =>
          tablePath.map((part) => `"${part}"`).join("."),
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
    case "databricks":
    case "datafusion":
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
    const tablePath = [table.name];

    // Set the fully qualified table name based on schema and database
    if (isSchemaless(schema)) {
      if (database !== defaultDatabase) {
        tablePath.unshift(database);
      }
    } else {
      // Include schema if it's not the default schema
      if (schema !== defaultSchema) {
        tablePath.unshift(schema);
      }

      // Include database if it's not the default database
      if (database !== defaultDatabase) {
        tablePath.unshift(database);
      }
    }

    const formatter = getFormatter(dialect);
    const formattedTableName = formatter.formatTablePath(tablePath);
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
