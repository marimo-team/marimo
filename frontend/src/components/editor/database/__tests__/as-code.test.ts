/* Copyright 2024 Marimo. All rights reserved. */
import { describe, test, expect } from "vitest";
import { generateDatabaseCode } from "../as-code";
import type { DatabaseConnection } from "../schemas";

describe("generateDatabaseCode", () => {
  const postgresConnection: DatabaseConnection = {
    type: "postgres",
    host: "localhost",
    port: 5432,
    database: "test",
    username: "user",
    password: "pass",
    ssl: true,
  };

  const mysqlConnection: DatabaseConnection = {
    type: "mysql",
    host: "localhost",
    port: 3306,
    database: "test",
    username: "user",
    password: "pass",
    ssl: true,
  };

  const sqliteConnection: DatabaseConnection = {
    type: "sqlite",
    database: "/path/to/db.sqlite",
  };

  const duckdbConnection: DatabaseConnection = {
    type: "duckdb",
    database: "data.duckdb",
    read_only: true,
  };

  const snowflakeConnection: DatabaseConnection = {
    type: "snowflake",
    account: "account",
    username: "user",
    password: "pass",
    warehouse: "warehouse",
    database: "db",
    schema: "schema",
    role: "role",
  };

  const bigqueryConnection: DatabaseConnection = {
    type: "bigquery",
    project: "my-project",
    dataset: "my_dataset",
    credentials_json: '{"type": "service_account", "project_id": "test"}',
  };

  test("postgres with SQLModel", () => {
    expect(
      generateDatabaseCode(postgresConnection, "sqlmodel"),
    ).toMatchSnapshot();
  });

  test("postgres with SQLAlchemy", () => {
    expect(
      generateDatabaseCode(postgresConnection, "sqlalchemy"),
    ).toMatchSnapshot();
  });

  test("postgres without SSL", () => {
    expect(
      generateDatabaseCode({ ...postgresConnection, ssl: false }),
    ).toMatchSnapshot();
  });

  test("mysql with SQLModel", () => {
    expect(generateDatabaseCode(mysqlConnection, "sqlmodel")).toMatchSnapshot();
  });

  test("mysql with SQLAlchemy", () => {
    expect(
      generateDatabaseCode(mysqlConnection, "sqlalchemy"),
    ).toMatchSnapshot();
  });

  test("mysql without SSL", () => {
    expect(
      generateDatabaseCode({ ...mysqlConnection, ssl: false }),
    ).toMatchSnapshot();
  });

  test("sqlite with SQLModel", () => {
    expect(
      generateDatabaseCode(sqliteConnection, "sqlmodel"),
    ).toMatchSnapshot();
  });

  test("sqlite with SQLAlchemy", () => {
    expect(
      generateDatabaseCode(sqliteConnection, "sqlalchemy"),
    ).toMatchSnapshot();
  });

  test("duckdb with SQLModel", () => {
    expect(
      generateDatabaseCode(duckdbConnection, "sqlmodel"),
    ).toMatchSnapshot();
  });

  test("duckdb with SQLAlchemy", () => {
    expect(
      generateDatabaseCode(duckdbConnection, "sqlalchemy"),
    ).toMatchSnapshot();
  });

  test("duckdb in-memory", () => {
    expect(
      generateDatabaseCode({ ...duckdbConnection, database: undefined }),
    ).toMatchSnapshot();
  });

  test("snowflake with SQLModel", () => {
    expect(
      generateDatabaseCode(snowflakeConnection, "sqlmodel"),
    ).toMatchSnapshot();
  });

  test("snowflake with SQLAlchemy", () => {
    expect(
      generateDatabaseCode(snowflakeConnection, "sqlalchemy"),
    ).toMatchSnapshot();
  });

  test("snowflake without role", () => {
    const { role, ...rest } = snowflakeConnection;
    expect(generateDatabaseCode(rest)).toMatchSnapshot();
  });

  test("bigquery with SQLModel", () => {
    expect(
      generateDatabaseCode(bigqueryConnection, "sqlmodel"),
    ).toMatchSnapshot();
  });

  test("bigquery with SQLAlchemy", () => {
    expect(
      generateDatabaseCode(bigqueryConnection, "sqlalchemy"),
    ).toMatchSnapshot();
  });

  test("throws for unsupported ORMs", () => {
    // @ts-expect-error - Testing invalid input
    expect(() => generateDatabaseCode(postgresConnection, "polars")).toThrow();
  });
});
