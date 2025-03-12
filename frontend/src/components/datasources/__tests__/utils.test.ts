/* Copyright 2024 Marimo. All rights reserved. */
import type { SQLTableContext } from "@/core/datasets/data-source-connections";
import type { DataTable, DataTableColumn } from "@/core/kernel/messages";
import { describe, it, expect } from "vitest";
import { sqlCode } from "../utils";

describe("sqlCode", () => {
  const mockTable: DataTable = {
    name: "users" as const,
    columns: [],
    source: "local",
    source_type: "local",
    type: "table",
  };
  const mockColumn = {
    name: "email" as const,
  } as DataTableColumn;
  const DEFAULT_ENGINE = "default_engine"; // Ensure this matches your actual default engine constant

  it("should generate basic SQL without sqlTableContext", () => {
    const result = sqlCode(mockTable, mockColumn.name);
    expect(result).toBe(
      "_df = mo.sql(f'SELECT \"email\" FROM users LIMIT 100')",
    );
  });

  it("should generate SQL with default schema", () => {
    const sqlTableContext: SQLTableContext = {
      engine: DEFAULT_ENGINE,
      schema: "public",
      defaultSchema: "public",
      database: "mydb",
    };

    const result = sqlCode(mockTable, mockColumn.name, sqlTableContext);
    expect(result).toBe('_df = mo.sql(f"SELECT email FROM users LIMIT 100")');
  });

  it("should generate SQL with non-default schema", () => {
    const sqlTableContext: SQLTableContext = {
      engine: DEFAULT_ENGINE,
      schema: "analytics",
      defaultSchema: "public",
      database: "mydb",
    };

    const result = sqlCode(mockTable, mockColumn.name, sqlTableContext);
    expect(result).toBe(
      '_df = mo.sql(f"SELECT email FROM mydb.analytics.users LIMIT 100")',
    );
  });

  it("should generate SQL with non-default engine", () => {
    const sqlTableContext: SQLTableContext = {
      engine: "snowflake",
      schema: "public",
      defaultSchema: "public",
      database: "mydb",
    };

    const result = sqlCode(mockTable, mockColumn.name, sqlTableContext);
    expect(result).toBe(
      '_df = mo.sql(f"SELECT email FROM users LIMIT 100", engine=snowflake)',
    );
  });

  it("should generate SQL with non-default schema and non-default engine", () => {
    const sqlTableContext: SQLTableContext = {
      engine: "bigquery",
      schema: "sales",
      defaultSchema: "public",
      database: "mydb",
    };

    const result = sqlCode(mockTable, mockColumn.name, sqlTableContext);
    expect(result).toBe(
      '_df = mo.sql(f"SELECT email FROM mydb.sales.users LIMIT 100", engine=bigquery)',
    );
  });
});
