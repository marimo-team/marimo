/* Copyright 2026 Marimo. All rights reserved. */

import { BigQueryDialect } from "@marimo-team/codemirror-sql/dialects";
import { isKnownDialect } from "@/core/codemirror/language/languages/sql/utils";
import type { SQLTableContext } from "@/core/datasets/data-source-connections";
import { DUCKDB_ENGINE } from "@/core/datasets/engines";
import type {
  Database,
  DatabaseSchema,
  DataTable,
  DataType,
} from "@/core/kernel/messages";
import { logNever } from "@/utils/assertNever";
import type { ColumnHeaderStatsKey } from "../data-table/types";

function tablePath(context: SQLTableContext, tableName: string): string[] {
  const segments = context.schemaPath?.length
    ? context.schemaPath
    : [context.schema];
  return [context.database, ...segments.filter(Boolean), tableName];
}

export function tableUniqueId(
  context: SQLTableContext | undefined,
  tableName: string,
): string {
  return context ? JSON.stringify(tablePath(context, tableName)) : tableName;
}

export function fullyQualifiedTableName(
  context: SQLTableContext | undefined,
  tableName: string,
): string {
  return context
    ? getFormatter(context.dialect).formatTablePath(
        tablePath(context, tableName),
      )
    : tableName;
}

// Some databases have no schemas, so we don't show it (eg. Clickhouse)
export function isSchemaless(schemaName: string) {
  return schemaName === "";
}

// Lazy discovery: the `*_resolved` flags default to `true` and are only `false`
// when enumeration was deferred. Helper functions to centralize logic
export function areSchemasResolved(database: Database): boolean {
  return database.schemas_resolved !== false;
}
export function areTablesResolved(schema: DatabaseSchema): boolean {
  return schema.tables_resolved !== false;
}
export function areChildSchemasResolved(schema: DatabaseSchema): boolean {
  return schema.child_schemas_resolved !== false;
}

/**
 * Whether a loaded schema subtree contains a table whose name matches
 * `searchValue`. Deferred (not-yet-fetched) tables and child schemas are
 * treated as non-matching, so searching never triggers a lazy catalog fetch on
 * large/remote connections.
 */
export function schemaSubtreeMatchesSearch(
  schema: DatabaseSchema,
  searchValue: string | undefined,
): boolean {
  const query = searchValue?.trim().toLowerCase();
  if (!query) {
    return false;
  }
  if (
    areTablesResolved(schema) &&
    schema.tables.some((table) => table.name.toLowerCase().includes(query))
  ) {
    return true;
  }
  if (areChildSchemasResolved(schema)) {
    return (schema.child_schemas ?? []).some((child) =>
      schemaSubtreeMatchesSearch(child, query),
    );
  }
  return false;
}

/**
 * Auto-expand a database row during search only when one of its loaded schemas
 * contains a matching table. Returns false when the schema list itself is
 * deferred.
 */
export function shouldExpandDatabaseForSearch(
  database: Database,
  searchValue: string | undefined,
): boolean {
  if (!searchValue?.trim() || !areSchemasResolved(database)) {
    return false;
  }
  return database.schemas.some((schema) =>
    schemaSubtreeMatchesSearch(schema, searchValue),
  );
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

function quoteIdentifier(identifier: string): string {
  return `"${identifier.replaceAll('"', '""')}"`;
}

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
          tablePath.map(quoteIdentifier).join("."),
        formatSelectClause: (columnName: string, tableName: string) =>
          `SELECT ${columnName === "*" ? "*" : quoteIdentifier(columnName)} FROM ${tableName} LIMIT 100`,
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
      schemaPath,
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
      const path = schemaPath?.length ? schemaPath : [schema];
      if (path.length > 1 || path[0] !== defaultSchema) {
        tablePath.unshift(...path);
      }

      // Nested schema names can also be attached catalog names.
      if (path.length > 1 || database !== defaultDatabase) {
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
