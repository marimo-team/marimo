/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { FieldOptions } from "@/components/forms/options";

function passwordField() {
  return z
    .string()
    .optional()
    .describe(
      FieldOptions.of({
        label: "Password",
        inputType: "password",
        placeholder: "password",
        optionRegex: ".*password.*",
      }),
    );
}

function tokenField() {
  return z
    .string()
    .optional()
    .describe(
      FieldOptions.of({
        label: "Token",
        inputType: "password",
        placeholder: "token",
        optionRegex: ".*token.*",
      }),
    );
}

function warehouseNameField() {
  return z
    .string()
    .optional()
    .describe(
      FieldOptions.of({
        label: "Warehouse Name",
        placeholder: "warehouse",
        optionRegex: ".*warehouse.*",
      }),
    );
}

function uriField() {
  return z
    .string()
    .optional()
    .describe(FieldOptions.of({ label: "URI", optionRegex: ".*uri.*" }));
}

function hostField() {
  return z
    .string()
    .nonempty()
    .describe(
      FieldOptions.of({
        label: "Host",
        placeholder: "localhost",
        optionRegex: ".*host.*",
      }),
    );
}

function databaseField() {
  return z.string().describe(
    FieldOptions.of({
      label: "Database",
      placeholder: "db name",
      optionRegex: ".*database.*",
    }),
  );
}

function schemaField() {
  return z.string().describe(
    FieldOptions.of({
      label: "Schema",
      placeholder: "schema name",
      optionRegex: ".*schema.*",
    }),
  );
}

function usernameField() {
  return z
    .string()
    .nonempty()
    .describe(
      FieldOptions.of({
        label: "Username",
        placeholder: "username",
        optionRegex: ".*username.*",
      }),
    );
}

function portField(defaultPort?: number) {
  const field = z.coerce
    .string()
    .describe(
      FieldOptions.of({
        label: "Port",
        inputType: "number",
        placeholder: defaultPort?.toString(),
      }),
    )
    .transform(Number)
    .refine((n) => n >= 0 && n <= 65_535, {
      message: "Port must be between 0 and 65535",
    });

  if (defaultPort !== undefined) {
    return field.default(defaultPort.toString());
  }

  return field;
}

function readOnlyField() {
  return z
    .boolean()
    .default(false)
    .describe(FieldOptions.of({ label: "Read Only" }));
}

export const PostgresConnectionSchema = z
  .object({
    type: z.literal("postgres"),
    host: hostField(),
    port: portField(5432).optional(),
    database: databaseField(),
    username: usernameField(),
    password: passwordField(),
    ssl: z
      .boolean()
      .default(false)
      .describe(FieldOptions.of({ label: "Use SSL" })),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const MySQLConnectionSchema = z
  .object({
    type: z.literal("mysql"),
    host: hostField(),
    port: portField(3306),
    database: databaseField(),
    username: usernameField(),
    password: passwordField(),
    ssl: z
      .boolean()
      .default(false)
      .describe(FieldOptions.of({ label: "Use SSL" })),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const SQLiteConnectionSchema = z
  .object({
    type: z.literal("sqlite"),
    database: databaseField().describe(
      FieldOptions.of({ label: "Database Path" }),
    ),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const DuckDBConnectionSchema = z
  .object({
    type: z.literal("duckdb"),
    database: databaseField().describe(
      FieldOptions.of({ label: "Database Path" }),
    ),
    read_only: readOnlyField(),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const SnowflakeConnectionSchema = z
  .object({
    type: z.literal("snowflake"),
    account: z
      .string()
      .nonempty()
      .describe(
        FieldOptions.of({
          label: "Account",
          optionRegex: ".*snowflake.*",
        }),
      ),
    warehouse: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Warehouse",
          optionRegex: ".*snowflake.*",
        }),
      ),
    database: databaseField(),
    schema: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Schema",
          optionRegex: ".*snowflake.*",
        }),
      ),
    username: usernameField(),
    password: passwordField(),
    role: z
      .string()
      .optional()
      .describe(FieldOptions.of({ label: "Role" })),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const BigQueryConnectionSchema = z
  .object({
    type: z.literal("bigquery"),
    project: z
      .string()
      .nonempty()
      .describe(
        FieldOptions.of({
          label: "Project ID",
          optionRegex: ".*bigquery.*",
        }),
      ),
    dataset: z
      .string()
      .nonempty()
      .describe(
        FieldOptions.of({
          label: "Dataset",
          optionRegex: ".*bigquery.*",
        }),
      ),
    credentials_json: z
      .string()
      .describe(
        FieldOptions.of({ label: "Credentials JSON", inputType: "textarea" }),
      ),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const ClickhouseConnectionSchema = z
  .object({
    type: z.literal("clickhouse_connect"),
    host: hostField(),
    port: portField(8123).optional(),
    username: usernameField(),
    password: passwordField(),
    secure: z
      .boolean()
      .default(false)
      .describe(FieldOptions.of({ label: "Use HTTPs" })),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const TimeplusConnectionSchema = z
  .object({
    type: z.literal("timeplus"),
    host: hostField().default("localhost"),
    port: portField(8123).optional(),
    username: usernameField().default("default"),
    password: passwordField().default(""),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const ChdbConnectionSchema = z
  .object({
    type: z.literal("chdb"),
    database: databaseField().describe(
      FieldOptions.of({ label: "Database Path" }),
    ),
    read_only: readOnlyField(),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const TrinoConnectionSchema = z
  .object({
    type: z.literal("trino"),
    host: hostField(),
    port: portField(8080),
    database: databaseField(),
    schema: schemaField().optional(),
    username: usernameField(),
    password: passwordField(),
    async_support: z
      .boolean()
      .default(false)
      .describe(FieldOptions.of({ label: "Async Support" })),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const IcebergConnectionSchema = z.object({
  type: z.literal("iceberg"),
  name: z.string().describe(FieldOptions.of({ label: "Catalog Name" })),
  catalog: z
    .discriminatedUnion("type", [
      z.object({
        type: z.literal("REST"),
        warehouse: warehouseNameField(),
        uri: z
          .string()
          .optional()
          .describe(
            FieldOptions.of({
              label: "URI",
              placeholder: "https://",
              optionRegex: ".*uri.*",
            }),
          ),
        token: tokenField(),
      }),
      z.object({
        type: z.literal("SQL"),
        warehouse: warehouseNameField(),
        uri: z
          .string()
          .optional()
          .describe(
            FieldOptions.of({
              label: "URI",
              placeholder: "jdbc:iceberg://host:port/database",
              optionRegex: ".*uri.*",
            }),
          ),
      }),
      z.object({
        type: z.literal("Hive"),
        warehouse: warehouseNameField(),
        uri: uriField(),
      }),
      z.object({
        type: z.literal("Glue"),
        warehouse: warehouseNameField(),
        uri: uriField(),
      }),
      z.object({
        type: z.literal("DynamoDB"),
        "dynamodb.profile-name": z
          .string()
          .optional()
          .describe(FieldOptions.of({ label: "Profile Name" })),
        "dynamodb.region": z
          .string()
          .optional()
          .describe(FieldOptions.of({ label: "Region" })),
        "dynamodb.access-key-id": z
          .string()
          .optional()
          .describe(FieldOptions.of({ label: "Access Key ID" })),
        "dynamodb.secret-access-key": z
          .string()
          .optional()
          .describe(
            FieldOptions.of({
              label: "Secret Access Key",
              inputType: "password",
            }),
          ),
        "dynamodb.session-token": z
          .string()
          .optional()
          .describe(
            FieldOptions.of({
              label: "Session Token",
              inputType: "password",
            }),
          ),
      }),
    ])
    .describe(FieldOptions.of({ special: "tabs" })),
});

export const DataFusionConnectionSchema = z.object({
  type: z.literal("datafusion"),
  sessionContext: z
    .boolean()
    .optional()
    .describe(
      FieldOptions.of({
        label: "Use Session Context",
      }),
    ),
});

// Ideally, we can conditionally render the username, host, and port fields.
export const PySparkConnectionSchema = z.object({
  type: z.literal("pyspark"),
  username: usernameField().optional(),
  host: hostField().optional(),
  port: portField().optional(),
});

export const DatabaseConnectionSchema = z.discriminatedUnion("type", [
  PostgresConnectionSchema,
  MySQLConnectionSchema,
  SQLiteConnectionSchema,
  DuckDBConnectionSchema,
  SnowflakeConnectionSchema,
  BigQueryConnectionSchema,
  ClickhouseConnectionSchema,
  TimeplusConnectionSchema,
  ChdbConnectionSchema,
  TrinoConnectionSchema,
  IcebergConnectionSchema,
  DataFusionConnectionSchema,
  PySparkConnectionSchema,
]);

export type DatabaseConnection = z.infer<typeof DatabaseConnectionSchema>;
