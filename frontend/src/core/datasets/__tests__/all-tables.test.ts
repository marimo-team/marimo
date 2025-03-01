/* Copyright 2024 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { datasetsAtom } from "../state";
import {
  allTablesAtom,
  dataSourceConnectionsAtom,
  DEFAULT_ENGINE,
} from "../data-source-connections";
import { store } from "@/core/state/jotai";
import type { DatasetsState } from "../types";

describe("allTablesAtom", () => {
  beforeEach(() => {
    // Reset the store before each test
    store.set(datasetsAtom, {
      tables: [],
    } as unknown as DatasetsState);
    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DEFAULT_ENGINE,
      connectionsMap: new Map().set(DEFAULT_ENGINE, {
        name: DEFAULT_ENGINE,
        dialect: "duckdb",
        source: "duckdb",
        display_name: "DuckDB In-Memory",
        databases: [],
      }),
    });
    vi.clearAllMocks();
  });

  it("should return dataset tables when only datasets are present", () => {
    // Set up test datasets
    const testDatasets = [
      {
        name: "dataset1",
        columns: [
          { name: "col1", type: "number" },
          { name: "col2", type: "string" },
        ],
      },
      {
        name: "dataset2",
        columns: [
          { name: "col3", type: "boolean" },
          { name: "col4", type: "date" },
        ],
      },
    ];
    store.set(datasetsAtom, { tables: testDatasets } as DatasetsState);

    // Get tables from the atom
    const tables = store.get(allTablesAtom);

    // Verify results
    expect(tables.size).toBe(2);
    expect(tables.has("dataset1")).toBe(true);
    expect(tables.has("dataset2")).toBe(true);
    expect(tables.get("dataset1")).toEqual(testDatasets[0]);
    expect(tables.get("dataset2")).toEqual(testDatasets[1]);
  });

  it("should return connection tables when only connections are present", () => {
    // Set up test connections
    const testConnection = {
      name: DEFAULT_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      default_schema: "main",
      databases: [
        {
          name: "db1",
          schemas: [
            {
              name: "main",
              tables: [
                { name: "table1", columns: [] },
                { name: "table2", columns: [] },
              ],
            },
          ],
        },
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DEFAULT_ENGINE,
      connectionsMap: new Map().set(DEFAULT_ENGINE, testConnection),
    });

    // Get tables from the atom
    const tables = store.get(allTablesAtom);

    // Verify results
    expect(tables.size).toBe(2);
    expect(tables.has("table1")).toBe(true);
    expect(tables.has("table2")).toBe(true);
    expect(tables.get("table1")).toEqual({ name: "table1", columns: [] });
  });

  it("should use schema name when there is no default schema", () => {
    // Set up test connection with no default schema
    const testConnection = {
      name: DEFAULT_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      databases: [
        {
          name: "db1",
          schemas: [
            {
              name: "schema1",
              tables: [{ name: "table1", columns: [] }],
            },
          ],
        },
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DEFAULT_ENGINE,
      connectionsMap: new Map().set(DEFAULT_ENGINE, testConnection),
    });

    // Get tables from the atom
    const tables = store.get(allTablesAtom);

    // Verify results
    expect(tables.size).toBe(1);
    expect(tables.has("schema1.table1")).toBe(true);
  });

  it("should use default schema appropriately", () => {
    // Set up test connection with a default schema
    const testConnection = {
      name: DEFAULT_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      default_schema: "default_schema",
      databases: [
        {
          name: "db1",
          schemas: [
            {
              name: "default_schema",
              tables: [
                { name: "table1", columns: [] },
                { name: "table2", columns: [] },
              ],
            },
            {
              name: "other_schema",
              tables: [{ name: "table3", columns: [] }],
            },
          ],
        },
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DEFAULT_ENGINE,
      connectionsMap: new Map().set(DEFAULT_ENGINE, testConnection),
    });

    // Get tables from the atom
    const tables = store.get(allTablesAtom);

    // Verify results
    expect(tables.size).toBe(3);
    expect(tables.has("table1")).toBe(true); // Using simple name due to default schema
    expect(tables.has("table2")).toBe(true); // Using simple name due to default schema
    expect(tables.has("other_schema.table3")).toBe(true); // Using schema-qualified name
  });

  it("should use fully qualified name when no default_database", () => {
    // Set up test connections with colliding schema.table names in different databases
    const testConnection = {
      name: DEFAULT_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      databases: [
        {
          name: "db1",
          schemas: [
            {
              name: "common_schema",
              tables: [{ name: "common_table", columns: [] }],
            },
          ],
        },
        {
          name: "db2",
          schemas: [
            {
              name: "common_schema",
              tables: [{ name: "common_table", columns: [] }],
            },
          ],
        },
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DEFAULT_ENGINE,
      connectionsMap: new Map().set(DEFAULT_ENGINE, testConnection),
    });

    const tables = store.get(allTablesAtom);

    expect(tables.size).toBe(2);
    expect(tables.has("db1.common_schema.common_table")).toBe(true);
    expect(tables.has("db2.common_schema.common_table")).toBe(true);
  });

  it("should handle default database", () => {
    // Set up test connection with a default database
    const testConnection = {
      name: DEFAULT_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      default_database: "db1",
      databases: [
        {
          name: "db1",
          schemas: [
            {
              name: "main",
              tables: [{ name: "table1", columns: [] }],
            },
          ],
        },
        {
          name: "db2",
          schemas: [
            {
              name: "main",
              tables: [{ name: "table1", columns: [] }],
            },
          ],
        },
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DEFAULT_ENGINE,
      connectionsMap: new Map().set(DEFAULT_ENGINE, testConnection),
    });

    // Get tables from the atom
    const tables = store.get(allTablesAtom);

    // Verify results
    expect(tables.size).toBe(2);
    expect(tables.has("main.table1")).toBe(true);
    expect(tables.has("db2.main.table1")).toBe(true);
  });

  it("should handle multiple connections with progressive qualified names", () => {
    const defaultConnection = {
      name: DEFAULT_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      databases: [
        {
          name: "same_db",
          schemas: [
            {
              name: "same_schema",
              tables: [{ name: "same_table", columns: [] }],
            },
          ],
        },
      ],
    };

    const otherConnection = {
      name: "other_engine",
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      databases: [
        {
          name: "same_db",
          schemas: [
            {
              name: "same_schema",
              tables: [{ name: "same_table", columns: [] }],
            },
          ],
        },
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DEFAULT_ENGINE,
      connectionsMap: new Map()
        .set(DEFAULT_ENGINE, defaultConnection)
        .set("other_engine", otherConnection),
    });

    // Get tables from the atom
    const tables = store.get(allTablesAtom);

    // Verify results
    expect(tables.size).toBe(2);
    expect(tables.has("same_schema.same_table")).toBe(true);
    expect(tables.has("same_db.same_schema.same_table")).toBe(true);
  });

  it("should handle both datasets and connection tables", () => {
    // Set up test datasets
    const testDatasets = [
      { name: "dataset1", columns: [] },
      { name: "table1", columns: [] }, // Intentional collision with connection table
    ];
    store.set(datasetsAtom, {
      tables: testDatasets,
    } as unknown as DatasetsState);

    const connectionTables = [
      { name: "table1", columns: [] }, // Collides with dataset
      { name: "conn_table", columns: [] },
    ];

    // Set up test connection
    const testConnection = {
      name: DEFAULT_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      default_database: "db1",
      default_schema: "main",
      databases: [
        {
          name: "db1",
          schemas: [
            {
              name: "main",
              tables: connectionTables,
            },
          ],
        },
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DEFAULT_ENGINE,
      connectionsMap: new Map().set(DEFAULT_ENGINE, testConnection),
    });

    // Get tables from the atom
    const tables = store.get(allTablesAtom);

    // Verify results - dataset should take precedence
    expect(tables.size).toBe(4);
    expect(tables.has("dataset1")).toBe(true);
    expect(tables.has("table1")).toBe(true); // Dataset takes precedence
    expect(tables.get("table1")).toEqual(testDatasets[1]);

    expect(tables.has("main.table1")).toBe(true); // Connection table gets schema-qualified
    expect(tables.get("main.table1")).toEqual(connectionTables[0]);
    expect(tables.has("conn_table")).toBe(true);
    expect(tables.get("conn_table")).toEqual(connectionTables[1]);
  });
});
