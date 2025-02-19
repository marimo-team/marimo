/* Copyright 2024 Marimo. All rights reserved. */
import { assertNever } from "@/utils/assertNever";
import { DatabaseConnectionSchema, type DatabaseConnection } from "./schemas";

export type ConnectionLibrary = "sqlmodel" | "sqlalchemy";
export const ConnectionDisplayNames: Record<ConnectionLibrary, string> = {
  sqlmodel: "SQLModel",
  sqlalchemy: "SQLAlchemy",
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

  const imports =
    orm === "sqlmodel"
      ? ["from sqlmodel import create_engine", "import os"]
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

    case "snowflake": {
      imports.push(
        "from snowflake.sqlalchemy import URL",
        "import sqlalchemy as sa",
      );

      const params = {
        account: connection.account,
        user: connection.username,
        password: `os.environ.get("SNOWFLAKE_PASSWORD", "${connection.password}")`,
        database: connection.database,
        warehouse: connection.warehouse,
        schema: connection.schema,
        role: connection.role,
      };

      const urlParams = Object.entries(params)
        .filter(([, v]) => v)
        .map(([k, v]) => `        ${k}=${v}`)
        .join(",\n");

      code = `
password = os.environ.get("SNOWFLAKE_PASSWORD", "${connection.password}")
engine = sa.create_engine(
    URL(
${urlParams}
    )
)
`;
      break;
    }

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

  return `${imports.join("\n")}\n${code.trim()}`;
}
