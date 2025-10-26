/* Copyright 2024 Marimo. All rights reserved. */

import {
  Cassandra,
  MariaSQL,
  MSSQL,
  MySQL,
  PLSQL,
  PostgreSQL,
  SQLDialect,
  type SQLDialectSpec,
  SQLite,
  StandardSQL,
} from "@codemirror/lang-sql";
import {
  BigQueryDialect,
  DuckDBDialect,
} from "@marimo-team/codemirror-sql/dialects";
import type { DataSourceConnection } from "@/core/kernel/messages";

const KNOWN_DIALECTS_ARRAY = [
  "postgresql",
  "postgres",
  "db2",
  "mysql",
  "sqlite",
  "mssql",
  "sqlserver",
  "duckdb",
  "mariadb",
  "cassandra",
  "noql",
  "athena",
  "bigquery",
  "hive",
  "redshift",
  "snowflake",
  "flink",
  "mongodb",
  "oracle",
  "oracledb",
  "timescaledb",
] as const;
const KNOWN_DIALECTS: ReadonlySet<string> = new Set(KNOWN_DIALECTS_ARRAY);
type KnownDialect = (typeof KNOWN_DIALECTS_ARRAY)[number];

export function isKnownDialect(dialect: string): dialect is KnownDialect {
  return KNOWN_DIALECTS.has(dialect);
}

/**
 * Guess the CodeMirror SQL dialect from the backend connection dialect.
 * If unknown, return the standard SQL dialect.
 */
export function guessDialect(
  connection: Pick<DataSourceConnection, "dialect">,
): SQLDialect {
  const dialect = connection.dialect;
  if (!isKnownDialect(dialect)) {
    return ModifiedStandardSQL;
  }

  switch (dialect) {
    case "postgresql":
    case "postgres":
      return PostgreSQL;
    case "mysql":
      return MySQL;
    case "sqlite":
      return SQLite;
    case "mssql":
    case "sqlserver":
      return MSSQL;
    case "duckdb":
      return DuckDBDialect;
    case "mariadb":
      return MariaSQL;
    case "cassandra":
      return Cassandra;
    case "oracledb":
    case "oracle":
      return PLSQL;
    case "bigquery":
      return BigQueryDialect;
    default:
      return ModifiedStandardSQL;
  }
}

const OpinionatedStandardSQL: SQLDialectSpec = {
  ...StandardSQL,
  // Upper-case identifiers do not need to be quoted most of the time
  caseInsensitiveIdentifiers: true,
  // Encase identifiers in single quotes instead of \
  identifierQuotes: "'",
};

export const ModifiedStandardSQL = SQLDialect.define(OpinionatedStandardSQL);
