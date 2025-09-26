/* Copyright 2024 Marimo. All rights reserved. */

import dedent from "string-dedent";
import { assertNever } from "@/utils/assertNever";
import { type DatabaseConnection, DatabaseConnectionSchema } from "./schemas";
import { isSecret, unprefixSecret } from "./secrets";

export type ConnectionLibrary =
  | "sqlmodel"
  | "sqlalchemy"
  | "duckdb"
  | "clickhouse_connect"
  | "chdb"
  | "pyiceberg"
  | "ibis"
  | "motherduck"
  | "redshift"
  | "databricks";

export const ConnectionDisplayNames: Record<ConnectionLibrary, string> = {
  sqlmodel: "SQLModel",
  sqlalchemy: "SQLAlchemy",
  duckdb: "DuckDB",
  clickhouse_connect: "ClickHouse Connect",
  chdb: "chDB",
  pyiceberg: "PyIceberg",
  ibis: "Ibis",
  motherduck: "MotherDuck",
  redshift: "Redshift",
  databricks: "Databricks",
};

abstract class CodeGenerator<T extends DatabaseConnection["type"]> {
  protected connection: Extract<DatabaseConnection, { type: T }>;
  protected orm: ConnectionLibrary;
  protected secrets: SecretContainer;

  constructor(
    connection: Extract<DatabaseConnection, { type: T }>,
    orm: ConnectionLibrary,
    secrets: SecretContainer,
  ) {
    this.connection = connection;
    this.orm = orm;
    this.secrets = secrets;
  }

  get imports(): Set<string> {
    const imports = new Set<string>(this.generateImports());
    switch (this.orm) {
      case "sqlalchemy":
        imports.add("import sqlalchemy");
        break;
      case "sqlmodel":
        imports.add("import sqlmodel");
        break;
      case "duckdb":
        imports.add("import duckdb");
        break;
    }
    return imports;
  }

  protected abstract generateImports(): string[];

  abstract generateConnectionCode(): string;
}

const makePrivate = (name: string) => `_${name}`;

class SecretContainer {
  private secrets: Record<string, string> = {};

  get imports(): Set<string> {
    if (Object.keys(this.secrets).length === 0) {
      return new Set<string>();
    }
    return new Set<string>(["import os"]);
  }

  print(
    varName: string,
    secretKeyOrValue: string | number | boolean,
    defaultValue?: string | undefined,
  ): string {
    varName = makePrivate(varName);
    if (isSecret(secretKeyOrValue)) {
      const withoutPrefix = unprefixSecret(secretKeyOrValue);
      const secretGetter = defaultValue
        ? `os.environ.get("${withoutPrefix}", "${defaultValue}")`
        : `os.environ.get("${withoutPrefix}")`;
      this.secrets[varName] = secretGetter;
      return varName;
    }
    if (defaultValue != null) {
      const secretGetter = `os.environ.get("${secretKeyOrValue}", "${defaultValue}")`;
      this.secrets[varName] = secretGetter;
      return varName;
    }

    if (typeof secretKeyOrValue === "number") {
      return `${secretKeyOrValue}`;
    }
    // If its a number, return it as is
    if (typeof secretKeyOrValue === "number") {
      return `${secretKeyOrValue}`;
    }
    if (typeof secretKeyOrValue === "boolean") {
      return formatBoolean(secretKeyOrValue);
    }
    if (!secretKeyOrValue) {
      return "";
    }

    return `"${secretKeyOrValue}"`;
  }

  printInFString(
    varName: string,
    secretKeyOrValue: string | number | undefined | boolean,
    defaultValue?: string | undefined,
  ): string {
    if (secretKeyOrValue === undefined) {
      return "";
    }
    // If its a number, return it as is
    if (typeof secretKeyOrValue === "number") {
      return `${secretKeyOrValue}`;
    }
    if (typeof secretKeyOrValue === "boolean") {
      return formatBoolean(secretKeyOrValue);
    }

    const value = this.print(varName, secretKeyOrValue, defaultValue);
    // If its a string, remove the quotes
    if (value.startsWith('"') && value.endsWith('"')) {
      return value.slice(1, -1);
    }
    // If its a variable, wrap it in curly braces
    return `{${value}}`;
  }

  /**
   * Generate a password variable for connection strings, supporting inline values,
   * environment variable lookups, and f-string formatting.
   * @param {string|undefined} password - Fallback password value.
   * @param {string} passwordPlaceholder - Environment variable name.
   * @param {boolean} inFString - If true, wrap for Python f-string.
   * @param {string} [variableName] - Variable name (default: "password").
   * @returns {string}
   *
   * @example
   * `printPassword("token123", "DATABRICKS_ACCESS_TOKEN", true, "access_token")`
   *
   * Returns:
   * ```python
   * _access_token = os.environ.get("DATABRICKS_ACCESS_TOKEN", "token123")
   * f"db://sample:{_access_token}@sample.com"
   * ```
   *
   * @example
   * `printPassword("token123", "DATABRICKS_ACCESS_TOKEN", false, "access_token")`
   *
   * Returns:
   * ```python
   * access_token = os.environ.get("DATABRICKS_ACCESS_TOKEN", "token123")
   * f"db://sample:access_token@sample.com"
   * ```
   */
  printPassword(
    password: string | undefined,
    passwordPlaceholder: string,
    inFString: boolean,
    variableName?: string,
  ): string {
    // Inline passwords should use printInFString, otherwise use print
    const printMethod = inFString
      ? this.printInFString.bind(this)
      : this.print.bind(this);

    return isSecret(password)
      ? printMethod(variableName || "password", password)
      : printMethod(variableName || "password", passwordPlaceholder, password);
  }

  getSecrets(): Record<string, string> {
    return this.secrets;
  }

  formatSecrets(): string {
    if (Object.keys(this.secrets).length === 0) {
      return "";
    }

    return Object.entries(this.secrets)
      .map(([k, v]) => `${k} = ${v}`)
      .join("\n");
  }
}

class PostgresGenerator extends CodeGenerator<"postgres"> {
  generateImports(): string[] {
    return [];
  }

  generateConnectionCode(): string {
    const ssl = this.connection.ssl
      ? ", connect_args={'sslmode': 'require'}"
      : "";
    const password = this.secrets.printPassword(
      this.connection.password,
      "POSTGRES_PASSWORD",
      true,
    );
    const username = this.secrets.printInFString(
      "username",
      this.connection.username,
    );
    const host = this.secrets.printInFString("host", this.connection.host);
    const port = this.secrets.printInFString("port", this.connection.port);
    const database = this.secrets.printInFString(
      "database",
      this.connection.database,
    );

    return dedent(`
      DATABASE_URL = f"postgresql://${username}:${password}@${host}:${port}/${database}"
      engine = ${this.orm}.create_engine(DATABASE_URL${ssl})
    `);
  }
}

class MySQLGenerator extends CodeGenerator<"mysql"> {
  generateImports(): string[] {
    return [];
  }

  generateConnectionCode(): string {
    const ssl = this.connection.ssl
      ? ", connect_args={'ssl': {'ssl-mode': 'preferred'}}"
      : "";
    const password = this.secrets.printPassword(
      this.connection.password,
      "MYSQL_PASSWORD",
      true,
    );
    const database = this.secrets.printInFString(
      "database",
      this.connection.database,
    );
    const username = this.secrets.printInFString(
      "username",
      this.connection.username,
    );
    const host = this.secrets.printInFString("host", this.connection.host);
    const port = this.secrets.printInFString("port", this.connection.port);

    return dedent(`
      DATABASE_URL = f"mysql+pymysql://${username}:${password}@${host}:${port}/${database}"
      engine = ${this.orm}.create_engine(DATABASE_URL${ssl})
    `);
  }
}

class SQLiteGenerator extends CodeGenerator<"sqlite"> {
  generateImports(): string[] {
    return [];
  }

  generateConnectionCode(): string {
    const database = this.connection.database
      ? this.secrets.printInFString("database", this.connection.database)
      : "";

    const databaseCode =
      database.startsWith("{") && database.endsWith("}")
        ? `DATABASE_URL = f"sqlite:///${database}"`
        : `DATABASE_URL = "sqlite:///${database}"`;

    return dedent(`
      ${databaseCode}
      engine = ${this.orm}.create_engine(DATABASE_URL)
    `);
  }
}

class SnowflakeGenerator extends CodeGenerator<"snowflake"> {
  generateImports(): string[] {
    return ["from snowflake.sqlalchemy import URL"];
  }

  generateConnectionCode(): string {
    const password = this.secrets.printPassword(
      this.connection.password,
      "SNOWFLAKE_PASSWORD",
      false,
    );
    const params = {
      account: this.secrets.print("account", this.connection.account),
      user: this.secrets.print("user", this.connection.username),
      database: this.secrets.print("database", this.connection.database),
      warehouse: this.connection.warehouse
        ? this.secrets.print("warehouse", this.connection.warehouse)
        : undefined,
      schema: this.connection.schema
        ? this.secrets.print("schema", this.connection.schema)
        : undefined,
      role: this.connection.role
        ? this.secrets.print("role", this.connection.role)
        : undefined,
      password: password,
    };

    return dedent(`
      engine = ${this.orm}.create_engine(
        URL(
${formatUrlParams(params, (inner) => `          ${inner}`)},
        )
      )
    `);
  }
}

class BigQueryGenerator extends CodeGenerator<"bigquery"> {
  generateImports(): string[] {
    return ["import json"];
  }

  generateConnectionCode(): string {
    const project = this.secrets.printInFString(
      "project",
      this.connection.project,
    );
    const dataset = this.secrets.printInFString(
      "dataset",
      this.connection.dataset,
    );

    return dedent(`
      credentials = json.loads("""${this.connection.credentials_json}""")
      engine = ${this.orm}.create_engine(f"bigquery://${project}/${dataset}", credentials_info=credentials)
    `);
  }
}

class DuckDBGenerator extends CodeGenerator<"duckdb"> {
  generateImports(): string[] {
    return [];
  }

  generateConnectionCode(): string {
    const database = this.secrets.printInFString(
      "database",
      this.connection.database || ":memory:",
    );

    return dedent(`
      DATABASE_URL = "${database}"
      engine = ${this.orm}.connect(DATABASE_URL, read_only=${formatBoolean(this.connection.read_only)})
    `);
  }
}

class MotherDuckGenerator extends CodeGenerator<"motherduck"> {
  generateImports(): string[] {
    return [];
  }

  generateConnectionCode(): string {
    const database = this.secrets.printInFString(
      "database",
      this.connection.database,
    );

    if (!this.connection.token) {
      return dedent(`
        conn = duckdb.connect("md:${database}")
        `);
    }

    const token = this.secrets.printPassword(
      this.connection.token,
      "MOTHERDUCK_TOKEN",
      false,
    );
    return dedent(`
      conn = duckdb.connect("md:${database}", config={"motherduck_token": ${token}})
    `);
  }
}

class ClickHouseGenerator extends CodeGenerator<"clickhouse_connect"> {
  generateImports(): string[] {
    return ["import clickhouse_connect"];
  }

  generateConnectionCode(): string {
    const password = this.secrets.printPassword(
      this.connection.password,
      "CLICKHOUSE_PASSWORD",
      false,
    );

    const params = {
      host: this.secrets.print("host", this.connection.host),
      user: this.secrets.print("user", this.connection.username),
      secure: this.secrets.print("secure", this.connection.secure),
      port: this.connection.port
        ? this.secrets.print("port", this.connection.port)
        : undefined,
      password: this.connection.password ? password : undefined,
    };

    return dedent(`
      engine = ${this.orm}.get_client(
${formatUrlParams(params, (inner) => `        ${inner}`)},
      )
    `);
  }
}

class TimeplusGenerator extends CodeGenerator<"timeplus"> {
  generateImports(): string[] {
    return [];
  }

  generateConnectionCode(): string {
    const password = this.secrets.printPassword(
      this.connection.password,
      "TIMEPLUS_PASSWORD",
      true,
    );
    const username = this.secrets.printInFString(
      "username",
      this.connection.username,
    );
    const host = this.secrets.printInFString("host", this.connection.host);
    const port = this.secrets.printInFString("port", this.connection.port);

    return dedent(`
      DATABASE_URL = f"timeplus://${username}:${password}@${host}:${port}"
      engine = ${this.orm}.create_engine(DATABASE_URL)
    `);
  }
}

class ChDBGenerator extends CodeGenerator<"chdb"> {
  generateImports(): string[] {
    return ["import chdb"];
  }

  generateConnectionCode(): string {
    const database =
      this.secrets.print("database", this.connection.database) || '""';

    return dedent(`
      engine = ${this.orm}.connect(${database}, read_only=${formatBoolean(this.connection.read_only)})
    `);
  }
}

class TrinoGenerator extends CodeGenerator<"trino"> {
  generateImports(): string[] {
    return this.connection.async_support
      ? ["import aiotrino"]
      : ["import trino.sqlalchemy"];
  }

  generateConnectionCode(): string {
    const trinoExtension = this.connection.async_support ? "aiotrino" : "trino";
    const schema = this.connection.schema ? `/${this.connection.schema}` : "";

    const username = this.secrets.printInFString(
      "username",
      this.connection.username,
    );
    const host = this.secrets.printInFString("host", this.connection.host);
    const port = this.secrets.printInFString("port", this.connection.port);
    const database = this.secrets.printInFString(
      "database",
      this.connection.database,
    );
    const password = this.secrets.printPassword(
      this.connection.password,
      "TRINO_PASSWORD",
      true,
    );

    return dedent(`
      engine = ${this.orm}.create_engine(f"${trinoExtension}://${username}:${password}@${host}:${port}/${database}${schema}")
    `);
  }
}

class PyIcebergGenerator extends CodeGenerator<"iceberg"> {
  generateImports(): string[] {
    switch (this.connection.catalog.type) {
      case "REST":
        return ["from pyiceberg.catalog.rest import RestCatalog"];
      case "SQL":
        return ["from pyiceberg.catalog.sql import SqlCatalog"];
      case "Hive":
        return ["from pyiceberg.catalog.hive import HiveCatalog"];
      case "Glue":
        return ["from pyiceberg.catalog.glue import GlueCatalog"];
      case "DynamoDB":
        return ["from pyiceberg.catalog.dynamodb import DynamoDBCatalog"];
      default:
        assertNever(this.connection.catalog);
    }
  }

  generateConnectionCode(): string {
    let options: Record<string, string | number | boolean> = {
      ...this.connection.catalog,
    };
    // Remove k='type' and v=nullish values
    options = Object.fromEntries(
      Object.entries(options).filter(
        ([k, v]) => v != null && v !== "" && k !== "type",
      ),
    );
    // Convert to secrets if they are secrets
    for (const [k, v] of Object.entries(options)) {
      if (isSecret(v)) {
        options[k] = this.secrets.print(k, v);
      } else if (typeof v === "string") {
        options[k] = `"${v}"`;
      }
    }

    const indent = "              ";
    const optionsAsPython = formatDictionaryEntries(
      options,
      (line) => `${indent}${line}`,
    );

    const name = `"${this.connection.name}"`;

    switch (this.connection.catalog.type) {
      case "REST":
        return dedent(`
          catalog = RestCatalog(
            ${name},
            **{\n${optionsAsPython}
            },
          )
        `);
      case "SQL":
        return dedent(`
          catalog = SqlCatalog(
            ${name},
            **{\n${optionsAsPython}
            },
          )
        `);
      case "Hive":
        return dedent(`
          catalog = HiveCatalog(
            ${name},
            **{\n${optionsAsPython}
            },
          )
        `);
      case "Glue":
        return dedent(`
          catalog = GlueCatalog(
            ${name},
            **{\n${optionsAsPython}
            },
          )
        `);
      case "DynamoDB":
        return dedent(`
          catalog = DynamoDBCatalog(
            ${name},
            **{\n${optionsAsPython}
            },
          )
        `);
      default:
        assertNever(this.connection.catalog);
    }
  }
}

class DataFusionGenerator extends CodeGenerator<"datafusion"> {
  generateImports(): string[] {
    // To trigger installation of ibis-datafusion
    return ["import ibis", "from datafusion import SessionContext"];
  }

  generateConnectionCode(): string {
    if (this.connection.sessionContext) {
      return dedent(`
        ctx = SessionContext()
        # Sample table
        _ = ctx.from_pydict({"a": [1, 2, 3]}, "my_table")

        con = ibis.datafusion.connect(ctx)
      `);
    }
    return dedent(`
      con = ibis.datafusion.connect()
    `);
  }
}

class PySparkGenerator extends CodeGenerator<"pyspark"> {
  generateImports(): string[] {
    return ["import ibis", "from pyspark.sql import SparkSession"];
  }

  generateConnectionCode(): string {
    if (this.connection.host || this.connection.port) {
      const host = this.secrets.printInFString("host", this.connection.host);
      const port = this.secrets.printInFString("port", this.connection.port);
      return dedent(`
        session = SparkSession.builder.remote(f"sc://${host}:${port}").getOrCreate()
        con = ibis.pyspark.connect(session)
      `);
    }
    return dedent(`
      con = ibis.pyspark.connect()
    `);
  }
}

class RedshiftGenerator extends CodeGenerator<"redshift"> {
  generateImports(): string[] {
    return ["import redshift_connector"];
  }

  generateConnectionCode(): string {
    const host = this.secrets.print("host", this.connection.host);
    const port = this.secrets.print("port", this.connection.port);
    const database = this.secrets.print("database", this.connection.database);

    if (this.connection.connectionType.type === "IAM credentials") {
      const accessKeyId = this.secrets.print(
        "aws_access_key_id",
        this.connection.connectionType.aws_access_key_id,
      );
      const secretAccessKey = this.secrets.print(
        "aws_secret_access_key",
        this.connection.connectionType.aws_secret_access_key,
      );
      const sessionToken = this.connection.connectionType.aws_session_token
        ? this.secrets.print(
            "aws_session_token",
            this.connection.connectionType.aws_session_token,
          )
        : undefined;

      const params = {
        iam: true,
        host: host,
        port: port,
        region: `"${this.connection.connectionType.region}"`,
        database: database,
        access_key_id: accessKeyId,
        secret_access_key: secretAccessKey,
        ...(sessionToken && { session_token: sessionToken }),
      };

      return dedent(`
        con = redshift_connector.connect(
${formatUrlParams(params, (inner) => `          ${inner}`)},
        )
      `);
    }

    // DB credentials
    const user = this.connection.connectionType.user
      ? this.secrets.print("user", this.connection.connectionType.user)
      : undefined;
    const password = this.connection.connectionType.password
      ? this.secrets.printPassword(
          this.connection.connectionType.password,
          "REDSHIFT_PASSWORD",
          false,
        )
      : undefined;

    const params = {
      host: host,
      port: port,
      database: database,
      ...(user && { user: user }),
      ...(password && { password: password }),
    };

    return dedent(`
      con = redshift_connector.connect(
${formatUrlParams(params, (inner) => `          ${inner}`)},
      )
    `);
  }
}

class DatabricksGenerator extends CodeGenerator<"databricks"> {
  generateImports(): string[] {
    return [];
  }

  generateConnectionCode(): string {
    const useFString = this.orm !== "ibis";

    const accessToken = this.secrets.printPassword(
      this.connection.access_token,
      "DATABRICKS_ACCESS_TOKEN",
      useFString,
      "access_token",
    );

    const serverHostname = this.secrets.printPassword(
      this.connection.server_hostname,
      "DATABRICKS_SERVER_HOSTNAME",
      useFString,
      "server_hostname",
    );

    const httpPath = this.secrets.printPassword(
      this.connection.http_path,
      "DATABRICKS_HTTP_PATH",
      useFString,
      "http_path",
    );

    const catalog = this.connection.catalog
      ? this.secrets.printInFString("catalog", this.connection.catalog)
      : undefined;
    const schema = this.connection.schema
      ? this.secrets.printInFString("schema", this.connection.schema)
      : undefined;

    let BASE_URL = `databricks://token:${accessToken}@${serverHostname}?http_path=${httpPath}`;
    if (catalog) {
      BASE_URL += `&catalog=${catalog}`;
    }
    if (schema) {
      BASE_URL += `&schema=${schema}`;
    }

    if (this.orm === "ibis") {
      const catalogParam = catalog ? `\n          catalog=${catalog},` : "";
      const schemaParam = schema ? `\n          schema=${schema},` : "";

      return dedent(`
        engine = ibis.databricks.connect(
          server_hostname=${serverHostname},
          http_path=${httpPath},${catalogParam}${schemaParam}
          access_token=${accessToken}
        )
      `);
    }

    return dedent(`
      DATABASE_URL = f"${BASE_URL}"
      engine = ${this.orm}.create_engine(DATABASE_URL)
      `);
  }
}

class CodeGeneratorFactory {
  public secrets = new SecretContainer();

  createGenerator(
    connection: DatabaseConnection,
    orm: ConnectionLibrary,
  ): CodeGenerator<DatabaseConnection["type"]> {
    switch (connection.type) {
      case "postgres":
        return new PostgresGenerator(connection, orm, this.secrets);
      case "mysql":
        return new MySQLGenerator(connection, orm, this.secrets);
      case "sqlite":
        return new SQLiteGenerator(connection, orm, this.secrets);
      case "snowflake":
        return new SnowflakeGenerator(connection, orm, this.secrets);
      case "bigquery":
        return new BigQueryGenerator(connection, orm, this.secrets);
      case "duckdb":
        return new DuckDBGenerator(connection, orm, this.secrets);
      case "motherduck":
        return new MotherDuckGenerator(connection, orm, this.secrets);
      case "clickhouse_connect":
        return new ClickHouseGenerator(connection, orm, this.secrets);
      case "timeplus":
        return new TimeplusGenerator(connection, orm, this.secrets);
      case "chdb":
        return new ChDBGenerator(connection, orm, this.secrets);
      case "trino":
        return new TrinoGenerator(connection, orm, this.secrets);
      case "iceberg":
        return new PyIcebergGenerator(connection, orm, this.secrets);
      case "datafusion":
        return new DataFusionGenerator(connection, orm, this.secrets);
      case "pyspark":
        return new PySparkGenerator(connection, orm, this.secrets);
      case "redshift":
        return new RedshiftGenerator(connection, orm, this.secrets);
      case "databricks":
        return new DatabricksGenerator(connection, orm, this.secrets);
      default:
        assertNever(connection);
    }
  }
}

export function generateDatabaseCode(
  connection: DatabaseConnection,
  orm: ConnectionLibrary,
): string {
  if (!(orm in ConnectionDisplayNames)) {
    throw new Error(`Unsupported library: ${orm}`);
  }

  // Parse the connection to ensure it's valid
  DatabaseConnectionSchema.parse(connection);

  const factory = new CodeGeneratorFactory();
  const generator = factory.createGenerator(connection, orm);
  const code = generator.generateConnectionCode();

  const secretsContainer = factory.secrets;

  const imports = new Set<string>([
    ...secretsContainer.imports,
    ...generator.imports,
  ]);

  const lines = [...imports].sort();
  lines.push("");
  const secrets = secretsContainer.formatSecrets();
  if (secrets) {
    lines.push(secrets);
  }
  lines.push(code.trim());
  return lines.join("\n");
}

function formatBoolean(value: boolean): string {
  return value.toString().charAt(0).toUpperCase() + value.toString().slice(1);
}

function formatUrlParams(
  params: Record<string, string | number | boolean | undefined>,
  formatLine: (line: string) => string,
): string {
  return Object.entries(params)
    .filter(([, v]) => v != null && v !== "")
    .map(([k, v]) => {
      if (typeof v === "boolean") {
        return formatLine(`${k}=${formatBoolean(v)}`);
      }
      if (typeof v === "number") {
        return formatLine(`${k}=${v}`);
      }
      return formatLine(`${k}=${v}`);
    })
    .join(",\n");
}

function formatDictionaryEntries(
  params: Record<string, string | number | boolean | undefined>,
  formatLine: (line: string) => string,
): string {
  return Object.entries(params)
    .filter(([, v]) => v != null && v !== "")
    .map(([k, v]) => {
      const key = `"${k}"`;
      if (typeof v === "boolean") {
        return formatLine(`${key}: ${formatBoolean(v)}`);
      }
      if (typeof v === "number") {
        return formatLine(`${key}: ${v}`);
      }
      return formatLine(`${key}: ${v}`);
    })
    .join(",\n");
}
