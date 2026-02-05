/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { DatasetTablesMap } from "@/core/datasets/data-source-connections";
import type { DataTable, DataTableColumn } from "@/core/kernel/messages";
import { type TableContextItem, TableContextProvider } from "../tables";

// Mock data for testing
const createMockColumn = (
  name: string,
  type: string,
  externalType?: string,
): DataTableColumn => ({
  name,
  type: type as DataTableColumn["type"],
  external_type: externalType || type,
  sample_values: [`sample_${name}_1`, `sample_${name}_2`],
});

const createMockTable = (
  name: string,
  options: Partial<DataTable> = {},
): DataTable => ({
  name,
  source: "memory",
  source_type: "local",
  type: "table",
  columns: [
    createMockColumn("id", "integer", "int64"),
    createMockColumn("name", "string", "varchar"),
    createMockColumn("active", "boolean", "bool"),
  ],
  num_rows: 100,
  num_columns: 3,
  engine: null,
  indexes: null,
  primary_keys: ["id"],
  variable_name: null,
  ...options,
});

describe("TableContextProvider", () => {
  describe("getItems", () => {
    it("should return empty array when no tables", () => {
      const tablesMap: DatasetTablesMap = new Map();
      const provider = new TableContextProvider(tablesMap);

      const items = provider.getItems();
      expect(items).toMatchSnapshot("empty-tables");
    });

    it("should return table items for single table", () => {
      const table = createMockTable("users");
      const tablesMap: DatasetTablesMap = new Map([["users", table]]);
      const provider = new TableContextProvider(tablesMap);

      const items = provider.getItems();
      expect(items).toMatchSnapshot("single-table");
    });

    it("should return table items for multiple tables", () => {
      const usersTable = createMockTable("users");
      const ordersTable = createMockTable("orders", {
        source: "database.db",
        source_type: "duckdb",
        type: "view",
        num_rows: 250,
        num_columns: 5,
        columns: [
          createMockColumn("order_id", "integer"),
          createMockColumn("user_id", "integer"),
          createMockColumn("amount", "number", "decimal"),
          createMockColumn("created_at", "string", "timestamp"),
          createMockColumn("status", "string", "enum"),
        ],
      });
      const tablesMap: DatasetTablesMap = new Map([
        ["users", usersTable],
        ["orders", ordersTable],
      ]);
      const provider = new TableContextProvider(tablesMap);

      const items = provider.getItems();
      expect(items).toMatchSnapshot("multiple-tables");
    });

    it("should handle dataframe tables with variable names", () => {
      const dfTable = createMockTable("df_analysis", {
        variable_name: "df_analysis",
        source: "pandas",
        source_type: "local",
        columns: [
          createMockColumn("timestamp", "string", "datetime64[ns]"),
          createMockColumn("value", "number", "float64"),
          createMockColumn("category", "string", "object"),
        ],
      });
      const tablesMap: DatasetTablesMap = new Map([["df_analysis", dfTable]]);
      const provider = new TableContextProvider(tablesMap);

      const items = provider.getItems();
      expect(items).toMatchSnapshot("dataframe-table");
    });

    it("should handle tables with minimal information", () => {
      const minimalTable = createMockTable("minimal", {
        columns: [],
        num_rows: null,
        num_columns: null,
        source: "",
        primary_keys: null,
        indexes: null,
      });
      const tablesMap: DatasetTablesMap = new Map([["minimal", minimalTable]]);
      const provider = new TableContextProvider(tablesMap);

      const items = provider.getItems();
      expect(items).toMatchSnapshot("minimal-table");
    });
  });

  describe("formatContext", () => {
    it("should format context for basic table", () => {
      const table = createMockTable("products");
      const item: TableContextItem = {
        type: "data",
        uri: "products",
        name: "products",
        description: "memory",
        data: table,
      };

      const tablesMap: DatasetTablesMap = new Map([["products", table]]);
      const provider = new TableContextProvider(tablesMap);

      const context = provider.formatContext(item);
      expect(context).toMatchSnapshot("basic-table-context");
    });

    it("should format context for table without shape info", () => {
      const table = createMockTable("no_shape", {
        num_rows: null,
        num_columns: null,
      });
      const item: TableContextItem = {
        type: "data",
        uri: "no_shape",
        name: "no_shape",
        description: "memory",
        data: table,
      };

      const tablesMap: DatasetTablesMap = new Map([["no_shape", table]]);
      const provider = new TableContextProvider(tablesMap);

      const context = provider.formatContext(item);
      expect(context).toMatchSnapshot("no-shape-table-context");
    });

    it("should format context for table without columns", () => {
      const table = createMockTable("no_columns", {
        columns: [],
      });
      const item: TableContextItem = {
        type: "data",
        uri: "no_columns",
        name: "no_columns",
        description: "memory",
        data: table,
      };

      const tablesMap: DatasetTablesMap = new Map([["no_columns", table]]);
      const provider = new TableContextProvider(tablesMap);

      const context = provider.formatContext(item);
      expect(context).toMatchSnapshot("no-columns-table-context");
    });

    it("should format context for remote database table", () => {
      const table = createMockTable("remote_table", {
        source: "postgresql://localhost:5432/mydb",
        source_type: "connection",
        engine: "postgresql",
        columns: [
          createMockColumn("uuid", "string", "uuid"),
          createMockColumn("created_at", "string", "timestamp with time zone"),
          createMockColumn("metadata", "string", "jsonb"),
        ],
      });
      const item: TableContextItem = {
        type: "data",
        uri: "remote_table",
        name: "remote_table",
        description: "postgresql://localhost:5432/mydb",
        data: table,
      };

      const tablesMap: DatasetTablesMap = new Map([["remote_table", table]]);
      const provider = new TableContextProvider(tablesMap);

      const context = provider.formatContext(item);
      expect(context).toMatchSnapshot("remote-table-context");
    });
  });

  describe("provider properties", () => {
    it("should have correct provider properties", () => {
      const tablesMap: DatasetTablesMap = new Map();
      const provider = new TableContextProvider(tablesMap);

      expect(provider.title).toBe("Tables");
      expect(provider.mentionPrefix).toBe("@");
      expect(provider.contextType).toBe("data");
    });
  });

  describe("createTableInfoElement", () => {
    it("should create info element for table with all properties", () => {
      const table = createMockTable("full_table", {
        source: "my_database.db",
        num_rows: 1000,
        num_columns: 5,
        columns: [
          createMockColumn("id", "integer", "bigint"),
          createMockColumn("name", "string", "varchar(255)"),
          createMockColumn("score", "number", "decimal(10,2)"),
        ],
      });
      const tablesMap: DatasetTablesMap = new Map([["full_table", table]]);
      const provider = new TableContextProvider(tablesMap);

      // @ts-expect-error - accessing private method for testing
      const element = provider.createTableInfoElement("full_table", table);

      expect(element.tagName).toBe("DIV");
      expect(element.classList.contains("mo-cm-tooltip")).toBe(true);
      expect(element.textContent).toMatchInlineSnapshot(
        `"full_tableSource: my_database.db1000 rows, 5 columnsColumnTypeMetadataidintegerPKnamestringscorenumber"`,
      );
    });

    it("should create info element for table without source", () => {
      const table = createMockTable("no_source", {
        source: "",
      });
      const tablesMap: DatasetTablesMap = new Map([["no_source", table]]);
      const provider = new TableContextProvider(tablesMap);

      // @ts-expect-error - accessing private method for testing
      const element = provider.createTableInfoElement("no_source", table);

      expect(element.textContent).toContain("no_source");
      expect(element.textContent).not.toContain("Source:");
    });

    it("should create info element for table without columns", () => {
      const table = createMockTable("no_cols", {
        columns: [],
      });
      const tablesMap: DatasetTablesMap = new Map([["no_cols", table]]);
      const provider = new TableContextProvider(tablesMap);

      // @ts-expect-error - accessing private method for testing
      const element = provider.createTableInfoElement("no_cols", table);

      expect(element.textContent).toContain("no_cols");
      // Should not contain a table element
      expect(element.querySelector("table")).toBeNull();
    });
  });
});
