/* Copyright 2026 Marimo. All rights reserved. */

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
import { logNever } from "@/utils/assertNever";
import { Logger } from "@/utils/Logger";

const KNOWN_DIALECTS_ARRAY = [
  "postgresql",
  "postgres",
  "couchbase",
  "db2",
  "db2i",
  "tidb",
  "mysql",
  "sqlite",
  "mssql",
  "sqlserver",
  "duckdb",
  "mariadb",
  "cassandra",
  "noql",
  "spark",
  "awsathena",
  "athena",
  "bigquery",
  "hive",
  "redshift",
  "snowflake",
  "flink",
  "mongodb",
  "trino",
  "oracle",
  "oracledb",
  "singlestoredb",
  "timescaledb",
  "databricks",
  "datafusion",
  "microsoft sql server",
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
    Logger.debug("Unknown dialect", { dialect });
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
    case "microsoft sql server":
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
    case "timescaledb":
      return PostgreSQL; // TimescaleDB is a PostgreSQL dialect
    case "awsathena":
    case "athena":
    case "db2i":
    case "db2":
    case "hive":
    case "redshift":
    case "snowflake":
    case "flink":
    case "mongodb":
    case "noql":
    case "couchbase":
    case "trino":
    case "tidb":
    case "singlestoredb":
    case "spark":
    case "databricks":
    case "datafusion":
      Logger.debug("Unsupported dialect", { dialect });
      return ModifiedStandardSQL;
    default:
      logNever(dialect);
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
