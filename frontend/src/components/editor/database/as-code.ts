/* Copyright 2024 Marimo. All rights reserved. */
import { assertNever } from "@/utils/assertNever";
import type { DatabaseConnection } from "./schemas";

type ConnectionLibrary = "sqlmodel" | "sqlalchemy";

const SUPPORTED_LIBRARIES = new Set<ConnectionLibrary>([
  "sqlmodel",
  "sqlalchemy",
]);

export function generateDatabaseCode(
  connection: DatabaseConnection,
  orm: ConnectionLibrary = "sqlmodel",
): string {
  if (!SUPPORTED_LIBRARIES.has(orm)) {
    throw new Error(`Unsupported library: ${orm}`);
  }

  const imports =
    orm === "sqlmodel"
      ? ["from sqlmodel import create_engine, Session", "import os"]
      : ["from sqlalchemy import create_engine", "import os"];

  let code = "";
  switch (connection.type) {
    case "postgres":
      code = `
password = os.environ.get("POSTGRES_PASSWORD", "${connection.password}")
DATABASE_URL = f"postgresql://${connection.username}:{password}@${connection.host}:${connection.port}/${connection.database}"
engine = create_engine(DATABASE_URL${connection.ssl ? ", connect_args={'sslmode': 'require'}" : ""})
`;
      break;

    case "mysql":
      code = `
password = os.environ.get("MYSQL_PASSWORD", "${connection.password}")
DATABASE_URL = f"mysql+pymysql://${connection.username}:{password}@${connection.host}:${connection.port}/${connection.database}"
engine = create_engine(DATABASE_URL${connection.ssl ? ", connect_args={'ssl': {'ssl-mode': 'preferred'}}" : ""})
`;
      break;

    case "sqlite":
      code = `
DATABASE_URL = "sqlite:///${connection.database}"
engine = create_engine(DATABASE_URL)
`;
      break;

    case "snowflake":
      imports.push("from sqlalchemy import URL");
      code = `
password = os.environ.get("SNOWFLAKE_PASSWORD", "${connection.password}")
connection_url = URL.create(
    "snowflake",
    username="${connection.username}",
    password=password,
    host="${connection.account}",
    database="${connection.database}",
    query={
        "warehouse": "${connection.warehouse}",
        "schema": "${connection.schema}"${connection.role ? `,\n        "role": "${connection.role}"` : ""}
    }
)
engine = create_engine(connection_url)
`;
      break;

    case "bigquery":
      imports.push("import json");
      code = `
credentials = json.loads("""${connection.credentials_json}""")
engine = create_engine(f"bigquery://${connection.project}/${connection.dataset}", credentials_info=credentials)
`;
      break;

    case "duckdb":
      code = `
engine = create_engine("duckdb:${connection.database || ":memory:"}"${connection.read_only ? ", read_only=True" : ""})
`;
      break;

    default:
      assertNever(connection);
  }

  return `${imports.join("\n")}\n${code.trim()}\n`;
}
