/* Copyright 2024 Marimo. All rights reserved. */

import type { SQLDialect } from "@codemirror/lang-sql";
import {
  Cassandra,
  MariaSQL,
  MSSQL,
  MySQL,
  PLSQL,
  PostgreSQL,
  SQLite,
} from "@codemirror/lang-sql";
import { DuckDBDialect } from "@marimo-team/codemirror-sql/dialects";
import type { DataSourceConnection } from "@/core/kernel/messages";

export function guessDialect(
  connection: DataSourceConnection,
): SQLDialect | undefined {
  switch (connection.dialect) {
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
    default:
      return undefined;
  }
}
