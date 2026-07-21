/* Copyright 2026 Marimo. All rights reserved. */
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
        optionRegex: "(password|passwd|pgpassword|db.?pass(word)?)",
      }),
    );
}

function tokenField(label?: string, required?: boolean) {
  let field: z.ZodString | z.ZodOptional<z.ZodString> = z.string();
  field = required ? field.nonempty() : field.optional();

  field = field.describe(
    FieldOptions.of({
      label: label || "Token",
      inputType: "password",
      optionRegex: "(token|api.?key|access.?token|auth.?token|pat)",
    }),
  );
  return field;
}

function warehouseNameField() {
  return z
    .string()
    .optional()
    .describe(
      FieldOptions.of({
        label: "Warehouse Name",
        optionRegex: "(warehouse|snowflake.?warehouse)",
      }),
    );
}

function uriField(label?: string, required?: boolean) {
  let field: z.ZodString | z.ZodOptional<z.ZodString> = z.string();
  field = required ? field.nonempty() : field.optional();

  return field.describe(
    FieldOptions.of({
      label: label || "URI",
      optionRegex: "(uri|url|connection.?string|database.?url|jdbc)",
    }),
  );
}

function hostField(label?: string) {
  return z
    .string()
    .nonempty()
    .describe(
      FieldOptions.of({
        label: label || "Host",
        // Exclude kubernetes/system host vars that match a naive "host" search.
        optionRegex:
          "^(?!.*(kubernetes|gpg)).*(host(name)?|pghost|db.?host|database.?host|mysql.?host|postgres.?host|server.?host)",
      }),
    );
}

function databaseField() {
  return z.string().describe(
    FieldOptions.of({
      label: "Database",
      optionRegex: "(database|db.?name|pgdatabase|^DB$|^DATABASE$)",
    }),
  );
}

function schemaField() {
  return z.string().describe(
    FieldOptions.of({
      label: "Schema",
      optionRegex: "(^SCHEMA$|db.?schema|postgres.?schema|pg.?schema|_SCHEMA$)",
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
        optionRegex: "(username|pguser|db.?user|^USER$|_USER$)",
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
    .refine((n: number) => n >= 0 && n <= 65_535, {
      message: "Port must be between 0 and 65535",
    });

  if (defaultPort !== undefined) {
    return field.default(defaultPort);
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

export const MotherDuckConnectionSchema = z
  .object({
    type: z.literal("motherduck"),
    database: databaseField()
      .default("my_db")
      .describe(FieldOptions.of({ label: "Database Name" })),
    token: tokenField(),
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
          optionRegex: "(snowflake.?account|^SNOWFLAKE_ACCOUNT$|account.?id)",
        }),
      ),
    warehouse: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Warehouse",
          optionRegex: "(snowflake.?warehouse|warehouse)",
        }),
      ),
    database: databaseField(),
    schema: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Schema",
          optionRegex: "(snowflake.?schema|^SCHEMA$|_SCHEMA$)",
        }),
      ),
    role: z
      .string()
      .optional()
      .describe(FieldOptions.of({ label: "Role" })),
    authType: z
      .discriminatedUnion("type", [
        z.object({
          type: z.literal("Password"),
          username: usernameField(),
          password: passwordField(),
          enable_mfa: z
            .boolean()
            .default(false)
            .describe(FieldOptions.of({ label: "Enable MFA (Duo Push)" })),
        }),
        z.object({
          type: z.literal("SSO (Browser)"),
          username: usernameField(),
        }),
        z.object({
          type: z.literal("Key Pair"),
          username: usernameField(),
          private_key_path: z
            .string()
            .nonempty()
            .describe(
              FieldOptions.of({
                label: "Private Key Path",
                placeholder: "/path/to/rsa_key.p8",
              }),
            ),
          private_key_passphrase: z
            .string()
            .optional()
            .describe(
              FieldOptions.of({
                label: "Private Key Passphrase",
                inputType: "password",
                optionRegex:
                  "(passphrase|private.?key.?passphrase|key.?passphrase)",
              }),
            ),
        }),
        z.object({
          type: z.literal("OAuth / PAT"),
          token: tokenField("Token", true),
        }),
      ])
      .default({
        type: "Password",
        username: "username",
        enable_mfa: false,
      })
      .describe(FieldOptions.of({ special: "tabs" })),
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
          optionRegex:
            "(bigquery.?project|gcp.?project|google.?cloud.?project|project.?id)",
        }),
      ),
    dataset: z
      .string()
      .nonempty()
      .describe(
        FieldOptions.of({
          label: "Dataset",
          optionRegex: "(bigquery.?dataset|dataset)",
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
    proxy_path: z
      .string()
      .optional()
      .describe(
        FieldOptions.of({
          label: "Proxy Path",
          placeholder: "/clickhouse",
        }),
      ),
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
              optionRegex: "(uri|url|connection.?string|database.?url|jdbc)",
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
              optionRegex: "(uri|url|connection.?string|database.?url|jdbc)",
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
          .describe(
            FieldOptions.of({
              label: "Access Key ID",
              inputType: "password",
              optionRegex: "(access.?key.?id|aws.?access.?key)",
            }),
          ),
        "dynamodb.secret-access-key": z
          .string()
          .optional()
          .describe(
            FieldOptions.of({
              label: "Secret Access Key",
              inputType: "password",
              optionRegex: "(secret.?access.?key|aws.?secret)",
            }),
          ),
        "dynamodb.session-token": z
          .string()
          .optional()
          .describe(
            FieldOptions.of({
              label: "Session Token",
              inputType: "password",
              optionRegex: "(session.?token|aws.?session)",
            }),
          ),
      }),
    ])
    .default({
      type: "REST",
      token: undefined,
    })
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
  host: hostField().optional(),
  port: portField().optional(),
});

// Ref: https://github.com/aws/amazon-redshift-python-driver/blob/master/tutorials/001%20-%20Connecting%20to%20Amazon%20Redshift.ipynb
export const RedshiftConnectionSchema = z
  .object({
    type: z.literal("redshift"),
    host: hostField(),
    port: portField(5439),
    connectionType: z
      .discriminatedUnion("type", [
        z.object({
          type: z.literal("IAM credentials"),
          region: z.string().describe(FieldOptions.of({ label: "Region" })),
          aws_access_key_id: z
            .string()
            .nonempty()
            .describe(
              FieldOptions.of({
                label: "AWS Access Key ID",
                inputType: "password",
                optionRegex: "(access.?key.?id|aws.?access.?key)",
              }),
            ),
          aws_secret_access_key: z
            .string()
            .nonempty()
            .describe(
              FieldOptions.of({
                label: "AWS Secret Access Key",
                inputType: "password",
                optionRegex: "(secret.?access.?key|aws.?secret)",
              }),
            ),
          aws_session_token: z
            .string()
            .optional()
            .describe(
              FieldOptions.of({
                label: "AWS Session Token",
                inputType: "password",
                optionRegex: "(session.?token|aws.?session)",
              }),
            ),
        }),
        z.object({
          type: z.literal("DB credentials"),
          user: usernameField(),
          password: passwordField(),
        }),
      ])
      .default({
        type: "IAM credentials",
        aws_access_key_id: "",
        aws_secret_access_key: "",
        region: "",
      }),
    database: databaseField(),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const DatabricksConnectionSchema = z
  .object({
    type: z.literal("databricks"),
    access_token: tokenField("Access Token", true),
    server_hostname: hostField("Server Hostname"),
    http_path: uriField("HTTP Path", true),
    catalog: z
      .string()
      .optional()
      .describe(FieldOptions.of({ label: "Catalog" })),
    schema: z
      .string()
      .optional()
      .describe(FieldOptions.of({ label: "Schema" })),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const SupabaseConnectionSchema = z
  .object({
    type: z.literal("supabase"),
    host: hostField(),
    port: portField(5432).optional(),
    database: databaseField(),
    username: usernameField(),
    password: passwordField(),
    disable_client_pooling: z
      .boolean()
      .default(false)
      .describe(
        FieldOptions.of({
          label: "Disable Client-Side Pooling",
        }),
      ),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const DatabaseConnectionSchema = z.discriminatedUnion("type", [
  PostgresConnectionSchema,
  MySQLConnectionSchema,
  SQLiteConnectionSchema,
  DuckDBConnectionSchema,
  MotherDuckConnectionSchema,
  SnowflakeConnectionSchema,
  BigQueryConnectionSchema,
  ClickhouseConnectionSchema,
  TimeplusConnectionSchema,
  ChdbConnectionSchema,
  TrinoConnectionSchema,
  IcebergConnectionSchema,
  DataFusionConnectionSchema,
  PySparkConnectionSchema,
  RedshiftConnectionSchema,
  DatabricksConnectionSchema,
  SupabaseConnectionSchema,
]);

export type DatabaseConnection = z.infer<typeof DatabaseConnectionSchema>;
