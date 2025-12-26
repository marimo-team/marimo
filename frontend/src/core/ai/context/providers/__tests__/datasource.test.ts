/* Copyright 2026 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { beforeEach, describe, expect, it } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type {
  ConnectionsMap,
  DatasetTablesMap,
} from "@/core/datasets/data-source-connections";
import { DUCKDB_ENGINE } from "@/core/datasets/engines";
import type { DataSourceConnection, DataTable } from "@/core/kernel/messages";
import { Boosts, Sections } from "../common";
import { DatasourceContextProvider, getDatasourceContext } from "../datasource";

// Mock data for testing
const createMockDataSourceConnection = (
  name: string,
  options: Partial<DataSourceConnection> = {},
): DataSourceConnection => ({
  name,
  dialect: "duckdb",
  source: "duckdb",
  display_name: `Test ${name}`,
  databases: [
    {
      name: "main",
      dialect: "duckdb",
      schemas: [
        {
          name: "public",
          tables: [
            {
              name: "users",
              source_type: "connection",
              source: name,
              num_rows: 100,
              num_columns: 3,
              variable_name: null,
              columns: [],
            },
            {
              name: "orders",
              source_type: "connection",
              source: name,
              num_rows: 50,
              num_columns: 4,
              variable_name: null,
              columns: [],
            },
          ],
        },
        {
          name: "analytics",
          tables: [
            {
              name: "events",
              source_type: "connection",
              source: name,
              num_rows: 200,
              num_columns: 5,
              variable_name: null,
              columns: [],
            },
          ],
        },
      ],
    },
  ],
  ...options,
});

const createMockConnectionsMap = (
  connections: DataSourceConnection[],
): ConnectionsMap => {
  const map = new Map();
  connections.forEach((conn) => {
    map.set(conn.name, conn);
  });
  return map;
};

const createMockDataTable = (
  name: string,
  options: Partial<DataTable> = {},
): DataTable => ({
  name,
  source: "local",
  source_type: "local",
  num_rows: 100,
  num_columns: 3,
  variable_name: name, // This makes it a dataframe
  columns: [
    {
      name: "id",
      type: "integer",
      external_type: "INTEGER",
      sample_values: [1, 2, 3],
    },
    {
      name: "name",
      type: "string",
      external_type: "VARCHAR",
      sample_values: ["Alice", "Bob", "Charlie"],
    },
    {
      name: "age",
      type: "integer",
      external_type: "INTEGER",
      sample_values: [25, 30, 35],
    },
  ],
  engine: null,
  indexes: null,
  primary_keys: null,
  type: "table",
  ...options,
});

const createMockTablesMap = (tables: DataTable[]): DatasetTablesMap => {
  const map = new Map();
  tables.forEach((table) => {
    map.set(table.name, table);
  });
  return map;
};

describe("DatasourceContextProvider", () => {
  let provider: DatasourceContextProvider;
  let connectionsMap: ConnectionsMap;
  let tablesMap: DatasetTablesMap;

  beforeEach(() => {
    connectionsMap = createMockConnectionsMap([
      createMockDataSourceConnection(DUCKDB_ENGINE),
      createMockDataSourceConnection("postgres", {
        dialect: "postgresql",
        source: "postgresql",
        display_name: "PostgreSQL Database",
        databases: [
          {
            name: "production",
            dialect: "postgresql",
            schemas: [
              {
                name: "public",
                tables: [
                  {
                    name: "customers",
                    source_type: "connection",
                    source: "postgres",
                    num_rows: 1000,
                    num_columns: 8,
                    variable_name: null,
                    columns: [],
                  },
                  {
                    name: "products",
                    source_type: "connection",
                    source: "postgres",
                    num_rows: 500,
                    num_columns: 6,
                    variable_name: null,
                    columns: [],
                  },
                  {
                    name: "sales",
                    source_type: "connection",
                    source: "postgres",
                    num_rows: 5000,
                    num_columns: 10,
                    variable_name: null,
                    columns: [],
                  },
                ],
              },
            ],
          },
        ],
      }),
    ]);
    tablesMap = createMockTablesMap([
      createMockDataTable("users"),
      createMockDataTable("orders"),
      createMockDataTable("events"),
    ]);
    provider = new DatasourceContextProvider(connectionsMap, tablesMap);
  });

  describe("provider properties", () => {
    it("should have correct provider properties", () => {
      expect(provider.title).toBe("Datasource");
      expect(provider.mentionPrefix).toBe("@");
      expect(provider.contextType).toBe("datasource");
    });
  });

  describe("getItems", () => {
    it("should return empty array when no connections", () => {
      const emptyMap = createMockConnectionsMap([]);
      const emptyProvider = new DatasourceContextProvider(emptyMap, new Map());
      const items = emptyProvider.getItems();
      expect(items).toEqual([]);
    });

    it("should return datasource items when connections exist", () => {
      const items = provider.getItems();

      expect(items).toHaveLength(2);

      // Check first item (duckdb)
      expect(items[0]).toMatchObject({
        name: DUCKDB_ENGINE,
        type: "datasource",
        data: {
          connection: {
            name: DUCKDB_ENGINE,
            dialect: "duckdb",
            source: "duckdb",
            display_name: `Test ${DUCKDB_ENGINE}`,
          },
        },
      });

      // Check second item (postgres)
      expect(items[1]).toMatchObject({
        name: "postgres",
        type: "datasource",
        data: {
          connection: {
            name: "postgres",
            dialect: "postgresql",
            source: "postgresql",
            display_name: "PostgreSQL Database",
          },
        },
      });

      // Check URIs are properly formatted
      expect(items[0].uri).toBe(`datasource://${DUCKDB_ENGINE}`);
      expect(items[1].uri).toBe("datasource://postgres");
    });

    it("should include dataframes for internal SQL engines", () => {
      const items = provider.getItems();
      const duckdbItem = items.find((item) => item.name === DUCKDB_ENGINE)!;

      // DuckDB is an internal engine, so it should have tables (dataframes)
      expect(duckdbItem.data.tables).toBeDefined();
      expect(duckdbItem.data.tables).toHaveLength(3);
      expect(duckdbItem.data.tables?.map((t) => t.name)).toEqual([
        "users",
        "orders",
        "events",
      ]);

      // PostgreSQL is external, so it should not have tables
      const postgresItem = items.find((item) => item.name === "postgres")!;
      expect(postgresItem.data.tables).toBeUndefined();
    });

    it("should handle connections with no databases", () => {
      const emptyDbConnection = createMockDataSourceConnection("empty", {
        databases: [],
      });
      const mapWithEmpty = createMockConnectionsMap([emptyDbConnection]);
      const providerWithEmpty = new DatasourceContextProvider(
        mapWithEmpty,
        new Map(),
      );

      const items = providerWithEmpty.getItems();
      expect(items).toHaveLength(0);
    });

    it("should handle connections with databases but no schemas", () => {
      const emptySchemaConnection = createMockDataSourceConnection(
        "empty-schema",
        {
          databases: [
            {
              name: "empty_db",
              dialect: "duckdb",
              schemas: [],
            },
          ],
        },
      );
      const mapWithEmptySchema = createMockConnectionsMap([
        emptySchemaConnection,
      ]);
      const providerWithEmptySchema = new DatasourceContextProvider(
        mapWithEmptySchema,
        new Map(),
      );

      const items = providerWithEmptySchema.getItems();
      expect(items).toHaveLength(1);
      expect(items[0].data.connection.databases[0].schemas).toEqual([]);
    });
  });

  describe("formatCompletion", () => {
    it("should format completion for datasource with tables", () => {
      const items = provider.getItems();
      const duckdbItem = items.find((item) => item.name === DUCKDB_ENGINE)!;
      const completion = provider.formatCompletion(duckdbItem);

      expect(completion).toMatchObject({
        label: "@In-Memory",
        displayLabel: "In-Memory",
        detail: "DuckDB",
        boost: Boosts.MEDIUM,
        type: "datasource",
        section: Sections.DATA_SOURCES,
      });

      expect(completion.info).toBeDefined();
    });

    it("should format completion for datasource with no tables", () => {
      const emptyConnection = createMockDataSourceConnection("empty", {
        databases: [
          {
            name: "empty_db",
            dialect: "duckdb",
            schemas: [
              {
                name: "empty_schema",
                tables: [],
              },
            ],
          },
        ],
      });
      const mapWithEmpty = createMockConnectionsMap([emptyConnection]);
      const providerWithEmpty = new DatasourceContextProvider(
        mapWithEmpty,
        new Map(),
      );

      const items = providerWithEmpty.getItems();
      const completion = provider.formatCompletion(items[0]);

      expect(completion.detail).toBe("DuckDB");
    });

    it("should format completion for postgres connection", () => {
      const items = provider.getItems();
      const postgresItem = items.find((item) => item.name === "postgres")!;
      const completion = provider.formatCompletion(postgresItem);

      expect(completion).toMatchObject({
        label: "@postgres",
        displayLabel: "postgres",
        detail: "PostgreSQL",
        boost: Boosts.MEDIUM,
        type: "datasource",
        section: Sections.DATA_SOURCES,
      });
    });

    it("should format completion for in-memory engine", () => {
      const duckdbConnection = createMockDataSourceConnection(DUCKDB_ENGINE, {
        dialect: "duckdb",
        source: "duckdb",
        display_name: "DuckDB (In-Memory)",
      });
      const mapWithInMemory = createMockConnectionsMap([duckdbConnection]);
      const providerWithInMemory = new DatasourceContextProvider(
        mapWithInMemory,
        new Map(),
      );
      const items = providerWithInMemory.getItems();
      const inMemoryItem = items.find((item) => item.name === DUCKDB_ENGINE)!;
      const completion = provider.formatCompletion(inMemoryItem);

      expect(completion).toMatchObject({
        label: "@In-Memory",
        displayLabel: "In-Memory",
        detail: "DuckDB",
        boost: Boosts.MEDIUM,
        type: "datasource",
        section: Sections.DATA_SOURCES,
      });
    });
  });

  describe("formatContext", () => {
    it("should format context for internal duckdb with multiple tables", () => {
      const items = provider.getItems();
      const duckdbItem = items.find((item) => item.name === DUCKDB_ENGINE)!;
      const context = provider.formatContext(duckdbItem);

      expect(context).not.toContain('"engine_name":"__marimo_duckdb"');
      expect(context).toMatchSnapshot("internal-datasource-context");
    });

    it("should include dataframes in context for internal engines", () => {
      const items = provider.getItems();
      const duckdbItem = items.find((item) => item.name === DUCKDB_ENGINE)!;
      const context = provider.formatContext(duckdbItem);

      // Should include the dataframes in the context
      expect(context).toContain('"name":"users"');
      expect(context).toContain('"name":"orders"');
      expect(context).toContain('"name":"events"');
      expect(context).toContain('"variable_name":"users"');
      expect(context).toContain('"variable_name":"orders"');
      expect(context).toContain('"variable_name":"events"');
    });

    it("should format context for postgres datasource", () => {
      const items = provider.getItems();
      const postgresItem = items.find((item) => item.name === "postgres")!;
      const context = provider.formatContext(postgresItem);

      expect(context).toContain('"engine_name":"postgres"');
      expect(context).toMatchSnapshot("postgres-datasource-context");
    });

    it("should format context for datasource with no tables", () => {
      const emptyConnection = createMockDataSourceConnection("empty", {
        databases: [
          {
            name: "empty_db",
            dialect: "duckdb",
            schemas: [
              {
                name: "empty_schema",
                tables: [],
              },
            ],
          },
        ],
      });
      const mapWithEmpty = createMockConnectionsMap([emptyConnection]);
      const providerWithEmpty = new DatasourceContextProvider(
        mapWithEmpty,
        new Map(),
      );

      const items = providerWithEmpty.getItems();
      const context = providerWithEmpty.formatContext(items[0]);

      expect(context).toContain('"dialect":"duckdb"');
      expect(context).not.toContain('"name":"Test empty"');
      expect(context).not.toContain('"source":"duckdb"');
      expect(context).not.toContain('"display_name":"Test empty"');
    });

    it("should format context for datasource with multiple databases", () => {
      const multiDbConnection = createMockDataSourceConnection("multi", {
        default_database: "db1",
        default_schema: "schema1",
        databases: [
          {
            name: "db1",
            dialect: "duckdb",
            schemas: [
              {
                name: "schema1",
                tables: [
                  {
                    name: "table1",
                    source_type: "connection",
                    source: "multi",
                    num_rows: 10,
                    num_columns: 2,
                    variable_name: null,
                    columns: [],
                  },
                  {
                    name: "table2",
                    source_type: "connection",
                    source: "multi",
                    num_rows: 20,
                    num_columns: 3,
                    variable_name: null,
                    columns: [],
                  },
                ],
              },
            ],
          },
          {
            name: "db2",
            dialect: "duckdb",
            schemas: [
              {
                name: "schema2",
                tables: [
                  {
                    name: "table3",
                    source_type: "connection",
                    source: "multi",
                    num_rows: 15,
                    num_columns: 4,
                    variable_name: null,
                    columns: [],
                  },
                ],
              },
              {
                name: "schema3",
                tables: [],
              },
            ],
          },
        ],
      });
      const mapWithMulti = createMockConnectionsMap([multiDbConnection]);
      const providerWithMulti = new DatasourceContextProvider(
        mapWithMulti,
        new Map(),
      );

      const items = providerWithMulti.getItems();
      const context = provider.formatContext(items[0]);

      expect(context).toContain('"dialect":"duckdb"');
      expect(context).toContain('"default_database":"db1"');
      expect(context).toContain('"default_schema":"schema1"');
      expect(context).toMatchSnapshot("multi-db-context");
    });
  });

  describe("edge cases", () => {
    it("should highlight default database and schema", () => {
      const connectionWithDefaults = createMockDataSourceConnection("test", {
        default_database: "main",
        default_schema: "public",
        databases: [
          {
            name: "main",
            dialect: "duckdb",
            schemas: [
              {
                name: "public",
                tables: [
                  {
                    name: "users",
                    source_type: "connection",
                    source: "test",
                    num_rows: 100,
                    num_columns: 3,
                    variable_name: null,
                    columns: [],
                  },
                ],
              },
              {
                name: "analytics",
                tables: [],
              },
            ],
          },
        ],
      });
      const mapWithDefaults = createMockConnectionsMap([
        connectionWithDefaults,
      ]);
      const providerWithDefaults = new DatasourceContextProvider(
        mapWithDefaults,
        new Map(),
      );

      const items = providerWithDefaults.getItems();
      const completion = providerWithDefaults.formatCompletion(items[0]);

      expect(completion.info).toBeDefined();
      expect(typeof completion.info).toBe("function");
    });

    it("should handle connections with special characters in names", () => {
      const specialConnection = createMockDataSourceConnection("test-db_123", {
        display_name: "Test DB (123)",
      });
      const mapWithSpecial = createMockConnectionsMap([specialConnection]);
      const providerWithSpecial = new DatasourceContextProvider(
        mapWithSpecial,
        new Map(),
      );

      const items = providerWithSpecial.getItems();
      expect(items).toHaveLength(1);
      expect(items[0].name).toBe("test-db_123");
      expect(items[0].uri).toBe("datasource://test-db_123");

      const context = providerWithSpecial.formatContext(items[0]);
      expect(context).toContain('"dialect":"duckdb"');
    });

    it("should handle very large numbers of tables", () => {
      const largeConnection = createMockDataSourceConnection("large", {
        databases: [
          {
            name: "large_db",
            dialect: "duckdb",
            schemas: [
              {
                name: "large_schema",
                tables: Array.from({ length: 100 }, (_, i) => ({
                  name: `table_${i}`,
                  source_type: "connection" as const,
                  source: "large",
                  num_rows: i + 1,
                  num_columns: 2,
                  variable_name: null,
                  columns: [],
                })),
              },
            ],
          },
        ],
      });
      const mapWithLarge = createMockConnectionsMap([largeConnection]);
      const providerWithLarge = new DatasourceContextProvider(
        mapWithLarge,
        new Map(),
      );

      const items = providerWithLarge.getItems();
      const completion = providerWithLarge.formatCompletion(items[0]);
      expect(completion.detail).toBe("DuckDB");

      const context = providerWithLarge.formatContext(items[0]);
      // Since we now return the entire data structure, check for basic properties
      expect(context).not.toContain('"name":"Test large"');
      expect(context).toContain('"dialect":"duckdb"');
      expect(context).not.toContain('"source":"duckdb"');
    });
  });
});

describe("getDatasourceContext", () => {
  it("should return null if no cell ID is found", () => {
    const context = getDatasourceContext("1" as CellId);
    expect(context).toBeNull();
  });
});
