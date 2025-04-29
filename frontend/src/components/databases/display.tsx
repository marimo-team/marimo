/* Copyright 2024 Marimo. All rights reserved. */
export function dbDisplayName(name: string) {
  switch (name) {
    case "duckdb":
      return "DuckDB";
    case "sqlite":
      return "SQLite";
    case "postgres":
    case "postgresql":
      return "PostgreSQL";
    case "mysql":
      return "MySQL";
    case "mariadb":
      return "MariaDB";
    case "mssql":
      return "Microsoft SQL Server";
    case "oracle":
      return "Oracle";
    case "redshift":
      return "Amazon Redshift";
    case "snowflake":
      return "Snowflake";
    case "bigquery":
      return "Google BigQuery";
    case "clickhouse":
      return "ClickHouse";
    case "timeplus":
      return "Timeplus";
    case "databricks":
      return "Databricks";
    case "db2":
      return "IBM Db2";
    case "hive":
      return "Apache Hive";
    case "impala":
      return "Apache Impala";
    case "presto":
      return "Presto";
    case "trino":
      return "Trino";
    case "cockroachdb":
      return "CockroachDB";
    case "timescaledb":
      return "TimescaleDB";
    case "singlestore":
      return "SingleStore";
    case "cassandra":
      return "Apache Cassandra";
    case "mongodb":
      return "MongoDB";
    case "iceberg":
      return "Apache Iceberg";
    default:
      return name;
  }
}

export function transformDisplayName(displayName: string): string {
  const [dbName, engineName] = displayName.split(" ");
  if (!engineName) {
    return dbDisplayName(displayName);
  }
  return `${dbDisplayName(dbName)} ${engineName}`;
}
