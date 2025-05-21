/* Copyright 2024 Marimo. All rights reserved. */
import type { FC } from "react";
import SQLiteIcon from "./icons/sqlite.svg";
import DuckDBIcon from "./icons/duckdb.svg";
import MotherDuckIcon from "./icons/motherduck.svg";
import PostgresQLIcon from "./icons/postgresql.svg";
import MySQLIcon from "./icons/mysql.svg";
import SnowflakeIcon from "./icons/snowflake.svg";
import DatabricksIcon from "./icons/databricks.svg";
import ClickhouseIcon from "./icons/clickhouse.svg";
import TimeplusIcon from "./icons/timeplus.svg";
import GoogleBigQueryIcon from "./icons/googlebigquery.svg";
import TrinoIcon from "./icons/trino.svg";
import IcebergIcon from "./icons/iceberg.png";
import DataFusionIcon from "./icons/datafusion.png";
import PySparkIcon from "./icons/spark.svg";
import { cn } from "@/utils/cn";
import { DatabaseIcon } from "lucide-react";

export type DBLogoName =
  | "sqlite"
  | "duckdb"
  | "motherduck"
  | "postgres"
  | "postgresql"
  | "mysql"
  | "snowflake"
  | "databricks"
  | "clickhouse"
  | "timeplus"
  | "bigquery"
  | "trino"
  | "iceberg"
  | "datafusion"
  | "pyspark";

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
  motherduck: MotherDuckIcon,
  postgres: PostgresQLIcon,
  postgresql: PostgresQLIcon,
  mysql: MySQLIcon,
  snowflake: SnowflakeIcon,
  databricks: DatabricksIcon,
  clickhouse: ClickhouseIcon,
  timeplus: TimeplusIcon,
  bigquery: GoogleBigQueryIcon,
  trino: TrinoIcon,
  iceberg: IcebergIcon,
  datafusion: DataFusionIcon,
  pyspark: PySparkIcon,
};

export const DatabaseLogo: FC<DatabaseLogoProps> = ({ name, className }) => {
  const lowerName = name.toLowerCase();

  const url = URLS[lowerName as DBLogoName];

  if (!url) {
    // Shift the icon down a bit to align with the text
    return <DatabaseIcon className={cn("mt-0.5", className)} />;
  }

  return (
    <img
      src={url}
      alt={name}
      className={cn(
        "invert-[.5] dark:invert-[.7]",
        className,
        // Remove filters for PNG icons
        url.endsWith(".png") &&
          "brightness-100 dark:brightness-100 invert-0 dark:invert-0",
      )}
    />
  );
};
