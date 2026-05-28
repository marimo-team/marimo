/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { Database, DataTable } from "@/core/kernel/messages";
import { filterEmptyDatabases } from "../datasources";

function makeTable(name: string): DataTable {
  return {
    name,
    columns: [],
    source: "memory",
    source_type: "local",
    type: "table",
    engine: null,
    indexes: null,
    num_columns: null,
    num_rows: null,
    variable_name: null,
    primary_keys: null,
  };
}

function makeDatabase(
  name: string,
  schemas: Array<{ name: string; tables: DataTable[] }>,
): Database {
  return {
    name,
    dialect: "duckdb",
    schemas,
    engine: null,
  };
}

describe("filterEmptyDatabases", () => {
  it("hides schemas with no tables", () => {
    const databases = [
      makeDatabase("memory", [
        { name: "main", tables: [makeTable("t1")] },
        { name: "empty_schema", tables: [] },
      ]),
    ];

    expect(filterEmptyDatabases(databases)).toEqual([
      makeDatabase("memory", [{ name: "main", tables: [makeTable("t1")] }]),
    ]);
  });

  it("hides databases where every schema is empty", () => {
    const databases = [
      makeDatabase("only_empty", [
        { name: "a", tables: [] },
        { name: "b", tables: [] },
      ]),
      makeDatabase("has_tables", [{ name: "main", tables: [makeTable("t1")] }]),
    ];

    expect(filterEmptyDatabases(databases)).toEqual([
      makeDatabase("has_tables", [{ name: "main", tables: [makeTable("t1")] }]),
    ]);
  });

  it("preserves databases with no schemas (lazy state)", () => {
    const databases = [makeDatabase("not_loaded_yet", [])];

    expect(filterEmptyDatabases(databases)).toEqual([
      makeDatabase("not_loaded_yet", []),
    ]);
  });

  it("returns an empty list when all databases are empty", () => {
    const databases = [
      makeDatabase("a", [{ name: "main", tables: [] }]),
      makeDatabase("b", [{ name: "main", tables: [] }]),
    ];

    expect(filterEmptyDatabases(databases)).toEqual([]);
  });

  it("does not mutate the input", () => {
    const databases = [
      makeDatabase("memory", [
        { name: "main", tables: [makeTable("t1")] },
        { name: "empty_schema", tables: [] },
      ]),
    ];
    const snapshot = JSON.parse(JSON.stringify(databases));

    filterEmptyDatabases(databases);

    expect(databases).toEqual(snapshot);
  });
});
