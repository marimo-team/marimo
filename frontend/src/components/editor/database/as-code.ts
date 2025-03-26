/* Copyright 2024 Marimo. All rights reserved. */
import { assertNever } from "@/utils/assertNever";
import { DatabaseConnectionSchema, type DatabaseConnection } from "./schemas";
// @ts-expect-error: no declaration file
import dedent from "string-dedent";

export type ConnectionLibrary =
  | "sqlmodel"
  | "sqlalchemy"
  | "duckdb"
  | "clickhouse_connect"
  | "chdb";
export const ConnectionDisplayNames: Record<ConnectionLibrary, string> = {
  sqlmodel: "SQLModel",
  sqlalchemy: "SQLAlchemy",
  duckdb: "DuckDB",
  clickhouse_connect: "ClickHouse Connect",
  chdb: "chDB",
};

export function generateDatabaseCode(
  connection: DatabaseConnection,
  orm: ConnectionLibrary,
): string {
  if (!(orm in ConnectionDisplayNames)) {
    throw new Error(`Unsupported library: ${orm}`);
  }

  // Parse the connection to ensure it's valid
  DatabaseConnectionSchema.parse(connection);

  const connectionsWithPasswords: Array<DatabaseConnection["type"]> = [
    "postgres",
    "mysql",
    "snowflake",
    "bigquery",
    "clickhouse_connect",
  ];

  const imports = connectionsWithPasswords.includes(connection.type)
    ? ["import os"]
    : [];

  switch (orm) {
    case "duckdb":
      imports.push("import duckdb");
      break;
    case "sqlmodel":
      imports.push("import sqlmodel");
      break;
    case "sqlalchemy":
      imports.push("import sqlalchemy");
      break;
    case "clickhouse_connect":
      imports.push("import clickhouse_connect");
      break;
    case "chdb":
      imports.push("import chdb");
      break;
    default:
      assertNever(orm);
  }

  let code = "";
  switch (connection.type) {
    case "postgres":
      code = dedent(`
        password = os.environ.get("POSTGRES_PASSWORD", "${connection.password}")
        DATABASE_URL = f"postgresql://${connection.username}:{password}@${connection.host}:${connection.port}/${connection.database}"
        engine = ${orm}.create_engine(DATABASE_URL${connection.ssl ? ", connect_args={'sslmode': 'require'}" : ""})
      `);
      break;

    case "mysql":
      code = dedent(`
        password = os.environ.get("MYSQL_PASSWORD", "${connection.password}")
        DATABASE_URL = f"mysql+pymysql://${connection.username}:{password}@${connection.host}:${connection.port}/${connection.database}"
        engine = ${orm}.create_engine(DATABASE_URL${connection.ssl ? ", connect_args={'ssl': {'ssl-mode': 'preferred'}}" : ""})
      `);
      break;

    case "sqlite":
      code = dedent(`
        DATABASE_URL = "sqlite:///${connection.database}"
        engine = ${orm}.create_engine(DATABASE_URL)
      `);
      break;

    case "snowflake": {
      imports.push("from snowflake.sqlalchemy import URL");

      const params = {
        account: connection.account,
        user: connection.username,
        password: connection.password,
        database: connection.database,
        warehouse: connection.warehouse,
        schema: connection.schema,
        role: connection.role,
      };

      code = dedent(`
        engine = ${orm}.create_engine(
          URL(
${formatUrlParams(params, (inner) => `            ${inner}`)},
            ${formatPassword(connection.password, "SNOWFLAKE_PASSWORD")}
          )
        )
      `);
      break;
    }

    case "bigquery":
      imports.push("import json");
      code = dedent(`
        credentials = json.loads("""${connection.credentials_json}""")
        engine = ${orm}.create_engine(f"bigquery://${connection.project}/${connection.dataset}", credentials_info=credentials)
      `);
      break;

    case "duckdb":
      code = dedent(`
        DATABASE_URL = ${connection.database ? `"${connection.database}"` : "':memory:'"}
        engine = ${orm}.connect(DATABASE_URL, read_only=${formatBoolean(connection.read_only)})
      `);
      break;

    case "clickhouse_connect": {
      const params = {
        host: connection.host,
        user: connection.username,
        secure: connection.secure,
        port: connection.port,
      };

      code = dedent(`
        engine = ${orm}.get_client(
${formatUrlParams(params, (inner) => `          ${inner}`)},
          ${formatPassword(connection.password, "CLICKHOUSE_PASSWORD")}
        )
      `);
      break;
    }

    case "chdb":
      code = dedent(`
        engine = ${orm}.connect("${connection.database}", read_only=${formatBoolean(connection.read_only)})
        `);
      break;

    default:
      assertNever(connection);
  }

  return `${imports.join("\n")}\n\n${code.trim()}`;
}

function formatPassword(password: string | undefined, envVar: string): string {
  if (!password) {
    return "";
  }
  return `os.environ.get("${envVar}", "${password}")`;
}

function formatBoolean(value: boolean): string {
  return value.toString().charAt(0).toUpperCase() + value.toString().slice(1);
}

function formatUrlParams(
  params: Record<string, string | number | boolean | undefined>,
  formatLine: (line: string) => string,
): string {
  return Object.entries(params)
    .filter(([, v]) => v)
    .map(([k, v]) => {
      if (typeof v === "boolean") {
        // uppercase the first letter, but do not quote it
        return formatLine(`${k}=${formatBoolean(v)}`);
      }
      if (typeof v === "number") {
        return formatLine(`${k}=${v}`);
      }
      return formatLine(`${k}="${v}"`);
    })
    .join(",\n");
}
