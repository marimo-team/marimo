/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { FieldOptions } from "@/components/forms/options";

export const PostgresConnectionSchema = z.object({
  type: z.literal("postgres"),
  host: z.string().describe(FieldOptions.of({ label: "Host" })),
  port: z
    .number()
    .default(5432)
    .describe(FieldOptions.of({ label: "Port" })),
  database: z.string().describe(FieldOptions.of({ label: "Database" })),
  username: z.string().describe(FieldOptions.of({ label: "Username" })),
  password: z.string().describe(FieldOptions.of({ label: "Password" })),
  ssl: z
    .boolean()
    .default(false)
    .describe(FieldOptions.of({ label: "Use SSL" })),
});

export const MySQLConnectionSchema = z.object({
  type: z.literal("mysql"),
  host: z.string().describe(FieldOptions.of({ label: "Host" })),
  port: z
    .number()
    .default(3306)
    .describe(FieldOptions.of({ label: "Port" })),
  database: z.string().describe(FieldOptions.of({ label: "Database" })),
  username: z.string().describe(FieldOptions.of({ label: "Username" })),
  password: z.string().describe(FieldOptions.of({ label: "Password" })),
  ssl: z
    .boolean()
    .default(false)
    .describe(FieldOptions.of({ label: "Use SSL" })),
});

export const SQLiteConnectionSchema = z.object({
  type: z.literal("sqlite"),
  database: z.string().describe(FieldOptions.of({ label: "Database Path" })),
});

export const DuckDBConnectionSchema = z.object({
  type: z.literal("duckdb"),
  database: z.string().describe(FieldOptions.of({ label: "Database Path" })),
  read_only: z
    .boolean()
    .default(false)
    .describe(FieldOptions.of({ label: "Read Only" })),
});

export const SnowflakeConnectionSchema = z.object({
  type: z.literal("snowflake"),
  account: z.string().describe(FieldOptions.of({ label: "Account" })),
  warehouse: z.string().describe(FieldOptions.of({ label: "Warehouse" })),
  database: z.string().describe(FieldOptions.of({ label: "Database" })),
  schema: z.string().describe(FieldOptions.of({ label: "Schema" })),
  username: z.string().describe(FieldOptions.of({ label: "Username" })),
  password: z.string().describe(FieldOptions.of({ label: "Password" })),
  role: z
    .string()
    .optional()
    .describe(FieldOptions.of({ label: "Role" })),
});

export const BigQueryConnectionSchema = z.object({
  type: z.literal("bigquery"),
  project: z.string().describe(FieldOptions.of({ label: "Project ID" })),
  dataset: z.string().describe(FieldOptions.of({ label: "Dataset" })),
  credentials_json: z
    .string()
    .describe(FieldOptions.of({ label: "Credentials JSON" })),
});

export const DatabaseConnectionSchema = z.discriminatedUnion("type", [
  PostgresConnectionSchema,
  MySQLConnectionSchema,
  SQLiteConnectionSchema,
  DuckDBConnectionSchema,
  SnowflakeConnectionSchema,
  BigQueryConnectionSchema,
]);

export type DatabaseConnection = z.infer<typeof DatabaseConnectionSchema>;
