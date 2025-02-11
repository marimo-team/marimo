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
      }),
    );
}

function hostField() {
  return z
    .string()
    .nonempty()
    .describe(FieldOptions.of({ label: "Host", placeholder: "localhost" }));
}

function databaseField() {
  return z
    .string()
    .describe(FieldOptions.of({ label: "Database", placeholder: "db name" }));
}

function usernameField() {
  return z
    .string()
    .nonempty()
    .describe(FieldOptions.of({ label: "Username", placeholder: "username" }));
}

function portField(defaultPort: number) {
  return z.coerce
    .string()
    .default(defaultPort.toString())
    .describe(
      FieldOptions.of({
        label: "Port",
        inputType: "number",
        placeholder: defaultPort.toString(),
      }),
    )
    .transform(Number)
    .refine((n) => n >= 0 && n <= 65_535, {
      message: "Port must be between 0 and 65535",
    });
}

export const PostgresConnectionSchema = z
  .object({
    type: z.literal("postgres"),
    host: hostField(),
    port: portField(5432),
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
    read_only: z
      .boolean()
      .default(false)
      .describe(FieldOptions.of({ label: "Read Only" })),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const SnowflakeConnectionSchema = z
  .object({
    type: z.literal("snowflake"),
    account: z
      .string()
      .nonempty()
      .describe(FieldOptions.of({ label: "Account" })),
    warehouse: z
      .string()
      .optional()
      .describe(FieldOptions.of({ label: "Warehouse" })),
    database: databaseField(),
    schema: z
      .string()
      .optional()
      .describe(FieldOptions.of({ label: "Schema" })),
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
      .describe(FieldOptions.of({ label: "Project ID" })),
    dataset: z
      .string()
      .nonempty()
      .describe(FieldOptions.of({ label: "Dataset" })),
    credentials_json: z
      .string()
      .describe(
        FieldOptions.of({ label: "Credentials JSON", inputType: "textarea" }),
      ),
  })
  .describe(FieldOptions.of({ direction: "two-columns" }));

export const DatabaseConnectionSchema = z.discriminatedUnion("type", [
  PostgresConnectionSchema,
  MySQLConnectionSchema,
  SQLiteConnectionSchema,
  DuckDBConnectionSchema,
  SnowflakeConnectionSchema,
  BigQueryConnectionSchema,
]);

export type DatabaseConnection = z.infer<typeof DatabaseConnectionSchema>;
