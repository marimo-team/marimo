/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { SQLTableContext } from "@/core/datasets/data-source-connections";
import { DUCKDB_ENGINE } from "@/core/datasets/engines";
import type { DataTable, DataTableColumn } from "@/core/kernel/messages";
import { sqlCode } from "../utils";

describe("sqlCode", () => {
  const mockTable: DataTable = {
    name: "users" as const,
    columns: [],
    source: "local",
    source_type: "local",
    type: "table",
    engine: null,
    indexes: null,
    num_columns: null,
    num_rows: null,
    variable_name: null,
    primary_keys: null,
  };
  const mockColumn = {
    name: "email" as const,
  } as DataTableColumn;

  describe("basic SQL generation", () => {
    it("should generate basic SQL without sqlTableContext", () => {
      const result = sqlCode({ table: mockTable, columnName: mockColumn.name });
      expect(result).toBe(
        "_df = mo.sql(f'SELECT \"email\" FROM users LIMIT 100')",
      );
    });

    it("should generate SQL with default schema", () => {
      const sqlTableContext: SQLTableContext = {
        engine: DUCKDB_ENGINE,
        schema: "public",
        defaultSchema: "public",
        defaultDatabase: "mydb",
        database: "mydb",
        dialect: "duckdb",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT "email" FROM "users" LIMIT 100\n""")',
      );
    });

    it("should generate SQL with non-default schema", () => {
      const sqlTableContext: SQLTableContext = {
        engine: DUCKDB_ENGINE,
        schema: "analytics",
        defaultSchema: "public",
        defaultDatabase: "mydb",
        database: "mydb",
        dialect: "duckdb",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT "email" FROM "analytics"."users" LIMIT 100\n""")',
      );
    });

    it("should generate SQL with non-default engine", () => {
      const sqlTableContext: SQLTableContext = {
        engine: "snowflake",
        schema: "public",
        defaultSchema: "public",
        defaultDatabase: "mydb",
        database: "mydb",
        dialect: "snowflake",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT email FROM users LIMIT 100\n""", engine=snowflake)',
      );
    });

    it("should generate SQL with non-default database", () => {
      const sqlTableContext: SQLTableContext = {
        engine: DUCKDB_ENGINE,
        schema: "public",
        defaultSchema: "public",
        defaultDatabase: "memory",
        database: "remote",
        dialect: "duckdb",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT "email" FROM "remote"."users" LIMIT 100\n""")',
      );
    });

    it("should generate SQL for schemaless tables", () => {
      const sqlTableContext: SQLTableContext = {
        engine: DUCKDB_ENGINE,
        schema: "",
        defaultDatabase: "mydb",
        database: "mydb",
        dialect: "duckdb",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT "email" FROM "users" LIMIT 100\n""")',
      );

      const sqlTableContext2: SQLTableContext = {
        engine: DUCKDB_ENGINE,
        schema: "",
        defaultDatabase: "remote",
        database: "another_db",
        dialect: "duckdb",
      };

      const result2 = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext: sqlTableContext2,
      });
      expect(result2).toBe(
        '_df = mo.sql(f"""\nSELECT "email" FROM "another_db"."users" LIMIT 100\n""")',
      );
    });
  });

  describe("BigQuery dialect", () => {
    it("should use backticks for table names", () => {
      const sqlTableContext: SQLTableContext = {
        engine: "bigquery",
        schema: "public",
        defaultSchema: "public",
        defaultDatabase: "mydb",
        database: "mydb",
        dialect: "bigquery",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT email FROM `users` LIMIT 100\n""", engine=bigquery)',
      );
    });

    it("should use backticks for database.schema.table", () => {
      const sqlTableContext: SQLTableContext = {
        engine: "bigquery",
        schema: "sales",
        defaultSchema: "public",
        defaultDatabase: "mydb",
        database: "remote",
        dialect: "bigquery",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT email FROM `remote.sales.users` LIMIT 100\n""", engine=bigquery)',
      );
    });

    it("should handle case-insensitive dialect name", () => {
      const sqlTableContext: SQLTableContext = {
        engine: "bigquery",
        schema: "public",
        defaultSchema: "public",
        defaultDatabase: "mydb",
        database: "mydb",
        dialect: "BigQuery",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT email FROM `users` LIMIT 100\n""", engine=bigquery)',
      );
    });
  });

  describe("MSSQL dialect", () => {
    it("should use TOP 100 instead of LIMIT", () => {
      const sqlTableContext: SQLTableContext = {
        engine: "mssql",
        schema: "dbo",
        defaultSchema: "dbo",
        defaultDatabase: "master",
        database: "master",
        dialect: "mssql",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT TOP 100 email FROM users\n""", engine=mssql)',
      );
    });

    it("should use TOP 100 with database and schema prefix", () => {
      const sqlTableContext: SQLTableContext = {
        engine: "mssql",
        schema: "sales",
        defaultSchema: "dbo",
        defaultDatabase: "master",
        database: "analytics",
        dialect: "mssql",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT TOP 100 email FROM analytics.sales.users\n""", engine=mssql)',
      );
    });
  });

  describe("TimescaleDB and PostgreSQL dialect", () => {
    it("should wrap table name with double quotes", () => {
      const sqlTableContext: SQLTableContext = {
        engine: "timescaledb",
        schema: "public",
        defaultSchema: "public",
        defaultDatabase: "mydb",
        database: "mydb",
        dialect: "timescaledb",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT "email" FROM "users" LIMIT 100\n""", engine=timescaledb)',
      );
    });

    it("should wrap database, schema, and table name with double quotes", () => {
      const sqlTableContext: SQLTableContext = {
        engine: "timescaledb",
        schema: "sales",
        defaultSchema: "public",
        defaultDatabase: "mydb",
        database: "remote",
        dialect: "timescaledb",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT "email" FROM "remote"."sales"."users" LIMIT 100\n""", engine=timescaledb)',
      );
    });

    it("should handle schemaless database with double quotes", () => {
      const sqlTableContext: SQLTableContext = {
        engine: "postgres",
        schema: "",
        defaultDatabase: "mydb",
        database: "remote",
        dialect: "postgres",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT "email" FROM "remote"."users" LIMIT 100\n""", engine=postgres)',
      );
    });

    it("should not quote * column name", () => {
      const sqlTableContext: SQLTableContext = {
        engine: "postgres",
        schema: "public",
        defaultSchema: "public",
        defaultDatabase: "mydb",
        database: "mydb",
        dialect: "postgres",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: "*",
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT * FROM "users" LIMIT 100\n""", engine=postgres)',
      );
    });
  });

  describe("fallback behavior", () => {
    it("should use default formatter for unknown dialect", () => {
      const sqlTableContext: SQLTableContext = {
        engine: "postgres",
        schema: "public",
        defaultSchema: "public",
        defaultDatabase: "mydb",
        database: "mydb",
        dialect: "unknown_dialect",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT email FROM users LIMIT 100\n""", engine=postgres)',
      );
    });

    it("should use default formatter when dialect is not provided", () => {
      const sqlTableContext: SQLTableContext = {
        engine: "postgres",
        schema: "public",
        defaultSchema: "public",
        defaultDatabase: "mydb",
        database: "mydb",
        dialect: "",
      };

      const result = sqlCode({
        table: mockTable,
        columnName: mockColumn.name,
        sqlTableContext,
      });
      expect(result).toBe(
        '_df = mo.sql(f"""\nSELECT email FROM users LIMIT 100\n""", engine=postgres)',
      );
    });
  });
});
