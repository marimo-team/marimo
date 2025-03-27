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

function portField(defaultPort: number, optional: boolean) {
  const field = z.coerce
    .string()
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

  return optional ? field.optional() : field.default(defaultPort.toString());
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
    port: portField(5432, false),
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
    port: portField(3306, false),
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

export const ClickhouseConnectionSchema = z
  .object({
    type: z.literal("clickhouse_connect"),
    host: hostField(),
    port: portField(8123, true),
    username: usernameField(),
    password: passwordField(),
    secure: z
      .boolean()
      .default(false)
      .describe(FieldOptions.of({ label: "Use HTTPs" })),
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

export const DatabaseConnectionSchema = z.discriminatedUnion("type", [
  PostgresConnectionSchema,
  MySQLConnectionSchema,
  SQLiteConnectionSchema,
  DuckDBConnectionSchema,
  SnowflakeConnectionSchema,
  BigQueryConnectionSchema,
  ClickhouseConnectionSchema,
  ChdbConnectionSchema,
]);

export type DatabaseConnection = z.infer<typeof DatabaseConnectionSchema>;
