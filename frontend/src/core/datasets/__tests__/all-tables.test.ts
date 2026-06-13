/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { store } from "@/core/state/jotai";
import {
  allTablesAtom,
  dataSourceConnectionsAtom,
} from "../data-source-connections";
import { DUCKDB_ENGINE } from "../engines";
import { datasetsAtom } from "../state";
import type { DatasetsState } from "../types";
import { databaseWithSchemas, makeTable } from "./catalog-fixtures";

describe("allTablesAtom", () => {
  beforeEach(() => {
    // Reset the store before each test
    store.set(datasetsAtom, {
      tables: [],
    } as unknown as DatasetsState);
    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map().set(DUCKDB_ENGINE, {
        name: DUCKDB_ENGINE,
        dialect: "duckdb",
        source: "duckdb",
        display_name: "DuckDB In-Memory",
        databases: [],
      }),
    });
    vi.clearAllMocks();
  });

  it("should return dataset tables when only datasets are present", () => {
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

    const tables = store.get(allTablesAtom);

    expect(tables.size).toBe(2);
    expect(tables.has("dataset1")).toBe(true);
    expect(tables.has("dataset2")).toBe(true);
    expect(tables.get("dataset1")).toEqual(testDatasets[0]);
    expect(tables.get("dataset2")).toEqual(testDatasets[1]);
  });

  it("should return connection tables when only connections are present", () => {
    const table1 = makeTable("table1");
    const table2 = makeTable("table2");
    const testConnection = {
      name: DUCKDB_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      default_schema: "main",
      databases: [
        databaseWithSchemas({
          name: "db1",
          dialect: "duckdb",
          schemas: [{ name: "main", tables: [table1, table2] }],
        }),
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map().set(DUCKDB_ENGINE, testConnection),
    });

    const tables = store.get(allTablesAtom);

    expect(tables.size).toBe(2);
    expect(tables.has("table1")).toBe(true);
    expect(tables.has("table2")).toBe(true);
    expect(tables.get("table1")).toEqual(table1);
    expect(tables.get("table2")).toEqual(table2);
  });

  it("should use schema name when there is no default schema", () => {
    const table1 = makeTable("table1");
    const testConnection = {
      name: DUCKDB_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      databases: [
        databaseWithSchemas({
          name: "db1",
          dialect: "duckdb",
          schemas: [{ name: "schema1", tables: [table1] }],
        }),
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map().set(DUCKDB_ENGINE, testConnection),
    });

    const tables = store.get(allTablesAtom);

    expect(tables.size).toBe(1);
    expect(tables.has("schema1.table1")).toBe(true);
    expect(tables.get("schema1.table1")).toEqual(table1);
  });

  it("should use default schema appropriately", () => {
    const table1 = makeTable("table1");
    const table2 = makeTable("table2");
    const table3 = makeTable("table3");
    const testConnection = {
      name: DUCKDB_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      default_schema: "default_schema",
      databases: [
        {
          ...databaseWithSchemas({
            name: "db1",
            dialect: "duckdb",
            schemas: [
              { name: "default_schema", tables: [table1, table2] },
              { name: "other_schema", tables: [table3] },
            ],
          }),
        },
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map().set(DUCKDB_ENGINE, testConnection),
    });

    const tables = store.get(allTablesAtom);

    expect(tables.size).toBe(3);
    expect(tables.has("table1")).toBe(true);
    expect(tables.has("table2")).toBe(true);
    expect(tables.has("other_schema.table3")).toBe(true);
    expect(tables.get("table1")).toEqual(table1);
    expect(tables.get("table2")).toEqual(table2);
    expect(tables.get("other_schema.table3")).toEqual(table3);
  });

  it("should use fully qualified name when no default_database", () => {
    const commonTable = makeTable("common_table");
    const testConnection = {
      name: DUCKDB_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      databases: [
        databaseWithSchemas({
          name: "db1",
          dialect: "duckdb",
          schemas: [{ name: "common_schema", tables: [commonTable] }],
        }),
        databaseWithSchemas({
          name: "db2",
          dialect: "duckdb",
          schemas: [{ name: "common_schema", tables: [commonTable] }],
        }),
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map().set(DUCKDB_ENGINE, testConnection),
    });

    const tables = store.get(allTablesAtom);

    expect(tables.size).toBe(2);
    expect(tables.has("db1.common_schema.common_table")).toBe(true);
    expect(tables.has("db2.common_schema.common_table")).toBe(true);
  });

  it("should handle default database", () => {
    const table1 = makeTable("table1");
    const testConnection = {
      name: DUCKDB_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      default_database: "db1",
      databases: [
        databaseWithSchemas({
          name: "db1",
          dialect: "duckdb",
          schemas: [{ name: "main", tables: [table1] }],
        }),
        databaseWithSchemas({
          name: "db2",
          dialect: "duckdb",
          schemas: [{ name: "main", tables: [table1] }],
        }),
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map().set(DUCKDB_ENGINE, testConnection),
    });

    const tables = store.get(allTablesAtom);

    expect(tables.size).toBe(2);
    expect(tables.has("main.table1")).toBe(true);
    expect(tables.has("db2.main.table1")).toBe(true);
  });

  it("should handle databases without a schema layer", () => {
    const table1 = makeTable("table1");
    const table2 = makeTable("table2");
    const testConnection = {
      name: DUCKDB_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      default_database: "db1",
      databases: [
        {
          name: "db1",
          dialect: "duckdb",
          children: [table1],
        },
        {
          name: "db2",
          dialect: "duckdb",
          children: [table2],
        },
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map().set(DUCKDB_ENGINE, testConnection),
    });

    const tables = store.get(allTablesAtom);

    expect(tables.size).toBe(2);
    expect(tables.get("table1")).toEqual(table1);
    expect(tables.get("db2.table2")).toEqual(table2);
  });

  it("should handle mixed flat and schema databases", () => {
    const table1 = makeTable("table1");
    const table2 = makeTable("table2");
    const table3 = makeTable("table3");
    const testConnection = {
      name: DUCKDB_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      default_database: "db1",
      databases: [
        {
          ...databaseWithSchemas({
            name: "db1",
            dialect: "duckdb",
            schemas: [
              { name: "central", tables: [table1] },
              { name: "main", tables: [table2] },
            ],
          }),
        },
        {
          name: "db2",
          dialect: "duckdb",
          children: [table3],
        },
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map().set(DUCKDB_ENGINE, testConnection),
    });

    const tables = store.get(allTablesAtom);

    expect(tables.size).toBe(3);
    expect(tables.get("central.table1")).toEqual(table1);
    expect(tables.get("main.table2")).toEqual(table2);
    expect(tables.get("db2.table3")).toEqual(table3);
  });

  it("should handle multiple connections with progressive qualified names", () => {
    const sameTable = makeTable("same_table");
    const defaultConnection = {
      name: DUCKDB_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      databases: [
        databaseWithSchemas({
          name: "same_db",
          dialect: "duckdb",
          schemas: [{ name: "same_schema", tables: [sameTable] }],
        }),
      ],
    };

    const otherConnection = {
      name: "other_engine",
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      databases: [
        databaseWithSchemas({
          name: "same_db",
          dialect: "duckdb",
          schemas: [{ name: "same_schema", tables: [sameTable] }],
        }),
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map()
        .set(DUCKDB_ENGINE, defaultConnection)
        .set("other_engine", otherConnection),
    });

    const tables = store.get(allTablesAtom);

    expect(tables.size).toBe(2);
    expect(tables.has("same_schema.same_table")).toBe(true);
    expect(tables.has("same_db.same_schema.same_table")).toBe(true);
  });

  it("should handle both datasets and connection tables", () => {
    const testDatasets = [
      { name: "dataset1", columns: [] },
      { name: "table1", columns: [] },
    ];
    store.set(datasetsAtom, {
      tables: testDatasets,
    } as unknown as DatasetsState);

    const connTable1 = makeTable("table1");
    const connTable2 = makeTable("conn_table");
    const testConnection = {
      name: DUCKDB_ENGINE,
      dialect: "duckdb",
      source: "duckdb",
      display_name: "DuckDB In-Memory",
      default_database: "db1",
      default_schema: "main",
      databases: [
        databaseWithSchemas({
          name: "db1",
          dialect: "duckdb",
          schemas: [{ name: "main", tables: [connTable1, connTable2] }],
        }),
      ],
    };

    store.set(dataSourceConnectionsAtom, {
      latestEngineSelected: DUCKDB_ENGINE,
      connectionsMap: new Map().set(DUCKDB_ENGINE, testConnection),
    });

    const tables = store.get(allTablesAtom);

    expect(tables.size).toBe(4);
    expect(tables.has("dataset1")).toBe(true);
    expect(tables.has("table1")).toBe(true);
    expect(tables.get("table1")).toEqual(testDatasets[1]);
    expect(tables.has("main.table1")).toBe(true);
    expect(tables.get("main.table1")).toEqual(connTable1);
    expect(tables.has("conn_table")).toBe(true);
    expect(tables.get("conn_table")).toEqual(connTable2);
  });
});
