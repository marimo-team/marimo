/* Copyright 2024 Marimo. All rights reserved. */
import type { FC } from "react";
import SQLiteIcon from "./icons/sqlite.svg";
import DuckDBIcon from "./icons/duckdb.svg";
import PostgresQLIcon from "./icons/postgresql.svg";
import MySQLIcon from "./icons/mysql.svg";
import SnowflakeIcon from "./icons/snowflake.svg";
import DatabricksIcon from "./icons/databricks.svg";
import ClickhouseIcon from "./icons/clickhouse.svg";
import TimeplusIcon from "./icons/timeplus.svg";
import GoogleBigQueryIcon from "./icons/googlebigquery.svg";
import TrinoIcon from "./icons/trino.svg";
import { cn } from "@/utils/cn";

export type DBLogoName =
  | "sqlite"
  | "duckdb"
  | "postgres"
  | "postgresql"
  | "mysql"
  | "snowflake"
  | "databricks"
  | "clickhouse"
  | "timeplus"
  | "bigquery"
  | "trino";

/**
 * Icons are from https://simpleicons.org/
 */

interface DatabaseLogoProps {
  name: string;
  className?: string;
}

const URLS: Record<DBLogoName, string | undefined> = {
  sqlite: SQLiteIcon,
  duckdb: DuckDBIcon,
  postgres: PostgresQLIcon,
  postgresql: PostgresQLIcon,
  mysql: MySQLIcon,
  snowflake: SnowflakeIcon,
  databricks: DatabricksIcon,
  clickhouse: ClickhouseIcon,
  timeplus: TimeplusIcon,
  bigquery: GoogleBigQueryIcon,
  trino: TrinoIcon,
};

export const DatabaseLogo: FC<DatabaseLogoProps> = ({ name, className }) => {
  const lowerName = name.toLowerCase();

  const url = URLS[lowerName as DBLogoName];

  if (!url) {
    return null;
  }

  return (
    <img
      src={url}
      alt={name}
      className={cn("invert-[.5] dark:invert-[.7]", className)}
    />
  );
};
