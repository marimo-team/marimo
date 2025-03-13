/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { type ConnectionLibrary, generateDatabaseCode } from "../as-code";
import type { DatabaseConnection } from "../schemas";

describe("generateDatabaseCode", () => {
  // Test fixtures
  const basePostgres: DatabaseConnection = {
    type: "postgres",
    host: "localhost",
    port: 5432,
    database: "test",
    username: "user",
    password: "pass",
    ssl: true,
  };

  const baseMysql: DatabaseConnection = {
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

  describe("basic connections", () => {
    it.each([
      ["postgres with SQLModel", basePostgres, "sqlmodel"],
      ["postgres with SQLAlchemy", basePostgres, "sqlalchemy"],
      ["mysql with SQLModel", baseMysql, "sqlmodel"],
      ["mysql with SQLAlchemy", baseMysql, "sqlalchemy"],
      ["sqlite", sqliteConnection, "sqlmodel"],
      ["duckdb", duckdbConnection, "sqlmodel"],
      ["snowflake", snowflakeConnection, "sqlmodel"],
      ["bigquery", bigqueryConnection, "sqlmodel"],
    ])("%s", (name, connection, orm) => {
      expect(
        generateDatabaseCode(connection, orm as ConnectionLibrary),
      ).toMatchSnapshot();
    });
  });

  describe("edge cases", () => {
    const testCases: Array<[string, DatabaseConnection, string]> = [
      [
        "postgres with special chars SQLModel",
        {
          ...basePostgres,
          password: "pass@#$%^&*",
          username: "user-name.special",
          database: "test-db.special",
        },
        "sqlmodel",
      ],
      [
        "postgres with special chars SQLAlchemy",
        {
          ...basePostgres,
          password: "pass@#$%^&*",
          username: "user-name.special",
          database: "test-db.special",
        },
        "sqlalchemy",
      ],
      [
        "snowflake with minimal config SQLModel",
        {
          type: "snowflake",
          account: "account",
          username: "user",
          password: "pass",
          database: "db",
          warehouse: "",
          schema: "",
          role: "",
        },
        "sqlmodel",
      ],
      [
        "postgres with unicode",
        {
          ...basePostgres,
          database: "测试数据库",
          username: "用户",
          password: "密码",
        },
        "sqlmodel",
      ],
      [
        "bigquery with long credentials",
        {
          ...bigqueryConnection,
          credentials_json: "x".repeat(10),
        },
        "sqlmodel",
      ],
      [
        "sqlite with empty path",
        {
          type: "sqlite",
          // sqlite allows empty path
          database: "",
        },
        "sqlmodel",
      ],
      [
        "postgres with IPv6",
        {
          ...basePostgres,
          host: "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
        },
        "sqlmodel",
      ],
      [
        "postgres with non-standard port",
        {
          ...basePostgres,
          port: 54_321,
        },
        "sqlmodel",
      ],
      [
        "mysql with max port",
        {
          ...baseMysql,
          port: 65_535,
        },
        "sqlmodel",
      ],
      [
        "postgres with URL-encoded characters",
        {
          ...basePostgres,
          database: "test%20db",
          username: "user%20name",
          password: "pass%20word",
        },
        "sqlmodel",
      ],
      [
        "mysql with extremely long database name",
        {
          ...baseMysql,
          database: "x".repeat(64),
        },
        "sqlmodel",
      ],
      [
        "snowflake with all optional fields filled",
        {
          type: "snowflake",
          account: "org-account",
          username: "user",
          password: "pass",
          database: "db",
          warehouse: "compute_wh",
          schema: "public",
          role: "accountadmin",
        },
        "sqlmodel",
      ],
      [
        "duckdb with relative path",
        {
          type: "duckdb",
          database: "./relative/path/db.duckdb",
          read_only: false,
        },
        "sqlmodel",
      ],
      [
        "postgres with domain socket",
        {
          ...basePostgres,
          host: "/var/run/postgresql",
          // @ts-expect-error - Testing invalid input
          port: undefined,
        },
        "sqlmodel",
      ],
    ];

    it.each(testCases)("%s", (name, connection, orm) => {
      expect(
        generateDatabaseCode(connection, orm as ConnectionLibrary),
      ).toMatchSnapshot();
    });
  });

  describe("security cases", () => {
    it.each([
      [
        "postgres with empty password",
        {
          ...basePostgres,
          password: "",
        },
      ],
      [
        "mysql with very long password",
        {
          ...baseMysql,
          password: "x".repeat(10),
        },
      ],
      [
        "postgres with SQL injection attempt in database name",
        {
          ...basePostgres,
          database: "db'; DROP TABLE users;--",
        },
      ],
      [
        "snowflake with sensitive info in account",
        {
          ...snowflakeConnection,
          account: "account-with-password123",
        },
      ],
      [
        "bigquery with malformed JSON",
        {
          ...bigqueryConnection,
          credentials_json: '{"type": "service_account", "project_id": "test"',
        },
      ],
    ])("%s", (name, connection) => {
      expect(generateDatabaseCode(connection, "sqlmodel")).toMatchSnapshot();
      expect(generateDatabaseCode(connection, "sqlalchemy")).toMatchSnapshot();
    });
  });

  describe("invalid cases", () => {
    it.each([
      [
        "throws for unsupported ORMs",
        () =>
          // @ts-expect-error - Testing invalid input
          generateDatabaseCode(basePostgres, "polars"),
      ],
      [
        "throws for invalid port",
        () => generateDatabaseCode({ ...basePostgres, port: -1 }, "sqlmodel"),
      ],
      [
        "throws for invalid host",
        () => generateDatabaseCode({ ...basePostgres, host: "" }, "sqlmodel"),
      ],
      [
        "throws for port out of range",
        () =>
          generateDatabaseCode({ ...basePostgres, port: 65_536 }, "sqlmodel"),
      ],
      [
        "throws for invalid snowflake account",
        () =>
          generateDatabaseCode(
            { ...snowflakeConnection, account: "" },
            "sqlmodel",
          ),
      ],
      [
        "throws for invalid bigquery project",
        () =>
          generateDatabaseCode(
            { ...bigqueryConnection, project: "" },
            "sqlmodel",
          ),
      ],
    ])("%s", (name, fn) => {
      expect(fn).toThrow();
    });
  });
});
