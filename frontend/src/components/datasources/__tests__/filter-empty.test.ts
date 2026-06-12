/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { CatalogNode } from "@/core/datasets/catalog";
import type {
  Database,
  DatabaseNamespace,
  DatabaseSchema,
  DataTable,
} from "@/core/kernel/messages";
import { filterEmptyDatabases } from "../datasources";

function makeTable(name: string): DataTable {
  return {
    kind: "data_table",
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

function makeSchema(opts: {
  name: string;
  tables: DataTable[];
  tables_resolved?: boolean;
}): DatabaseSchema {
  return {
    kind: "schema",
    name: opts.name,
    tables: opts.tables,
    tables_resolved: opts.tables_resolved ?? true,
  };
}

function makeNamespace(opts: {
  name: string;
  children?: CatalogNode[];
  children_resolved?: boolean;
}): DatabaseNamespace {
  return {
    kind: "namespace",
    name: opts.name,
    children: opts.children ?? [],
    children_resolved: opts.children_resolved ?? true,
  };
}

function makeDatabase(
  name: string,
  children: CatalogNode[],
  children_resolved = true,
): Database {
  return {
    name,
    dialect: "duckdb",
    children,
    children_resolved,
    engine: null,
  };
}

describe("filterEmptyDatabases", () => {
  it("hides schemas whose tables are resolved and empty", () => {
    const databases = [
      makeDatabase("memory", [
        makeSchema({ name: "main", tables: [makeTable("t1")] }),
        makeSchema({ name: "empty_schema", tables: [] }),
      ]),
    ];

    expect(filterEmptyDatabases(databases)).toEqual([
      makeDatabase("memory", [
        makeSchema({ name: "main", tables: [makeTable("t1")] }),
      ]),
    ]);
  });

  it("preserves databases whose children have not been resolved yet (lazy state)", () => {
    const databases = [
      makeDatabase("not_loaded_yet", [], /* children_resolved */ false),
    ];

    expect(filterEmptyDatabases(databases)).toEqual([
      makeDatabase("not_loaded_yet", [], false),
    ]);
  });

  it("hides databases that have been resolved as empty", () => {
    const databases = [
      makeDatabase("really_empty", [], /* children_resolved */ true),
      makeDatabase("has_tables", [
        makeSchema({ name: "main", tables: [makeTable("t1")] }),
      ]),
    ];

    expect(filterEmptyDatabases(databases)).toEqual([
      makeDatabase("has_tables", [
        makeSchema({ name: "main", tables: [makeTable("t1")] }),
      ]),
    ]);
  });

  it("hides databases whose children all filtered to empty", () => {
    const databases = [
      makeDatabase("only_empty", [
        makeSchema({ name: "a", tables: [] }),
        makeSchema({ name: "b", tables: [] }),
      ]),
      makeDatabase("has_tables", [
        makeSchema({ name: "main", tables: [makeTable("t1")] }),
      ]),
    ];

    expect(filterEmptyDatabases(databases)).toEqual([
      makeDatabase("has_tables", [
        makeSchema({ name: "main", tables: [makeTable("t1")] }),
      ]),
    ]);
  });

  it("treats missing children_resolved as resolved (backward compatible)", () => {
    const databases = [
      { name: "memory", dialect: "duckdb", children: [], engine: null },
    ] as Database[];

    expect(filterEmptyDatabases(databases)).toEqual([]);
  });

  it("preserves schemas whose tables have not been resolved yet", () => {
    const databases = [
      makeDatabase("snowflake_db", [
        makeSchema({ name: "public", tables: [], tables_resolved: false }),
        makeSchema({ name: "audit", tables: [], tables_resolved: false }),
        makeSchema({
          name: "really_empty",
          tables: [],
          tables_resolved: true,
        }),
      ]),
    ];

    expect(filterEmptyDatabases(databases)).toEqual([
      makeDatabase("snowflake_db", [
        makeSchema({ name: "public", tables: [], tables_resolved: false }),
        makeSchema({ name: "audit", tables: [], tables_resolved: false }),
      ]),
    ]);
  });

  it("treats missing tables_resolved as resolved (backward compatible)", () => {
    const databases = [
      makeDatabase("memory", [
        { kind: "schema", name: "main", tables: [makeTable("t1")] },
        { kind: "schema", name: "empty_schema", tables: [] },
      ] as DatabaseSchema[]),
    ];

    expect(filterEmptyDatabases(databases)).toEqual([
      makeDatabase("memory", [
        { kind: "schema", name: "main", tables: [makeTable("t1")] },
      ] as DatabaseSchema[]),
    ]);
  });

  it("returns the same reference when nothing was filtered", () => {
    const databases = [
      makeDatabase("memory", [
        makeSchema({ name: "main", tables: [makeTable("t1")] }),
      ]),
    ];

    expect(filterEmptyDatabases(databases)).toBe(databases);
  });

  it("does not mutate the input", () => {
    const databases = [
      makeDatabase("memory", [
        makeSchema({ name: "main", tables: [makeTable("t1")] }),
        makeSchema({ name: "empty_schema", tables: [] }),
      ]),
    ];
    const snapshot = JSON.parse(JSON.stringify(databases));

    filterEmptyDatabases(databases);

    expect(databases).toEqual(snapshot);
  });

  it("keeps a namespace that has only child namespaces (no own tables)", () => {
    const databases = [
      makeDatabase("iceberg", [
        makeNamespace({
          name: "top",
          children: [
            makeNamespace({
              name: "nested",
              children: [
                makeSchema({ name: "deep", tables: [makeTable("t1")] }),
              ],
            }),
          ],
        }),
      ]),
    ];

    expect(filterEmptyDatabases(databases)).toBe(databases);
  });

  it("preserves a namespace whose children are deferred", () => {
    const databases = [
      makeDatabase("iceberg", [
        makeNamespace({
          name: "top",
          children: [],
          children_resolved: false,
        }),
      ]),
    ];

    expect(filterEmptyDatabases(databases)).toBe(databases);
  });

  it("hides a nested namespace that is resolved-empty", () => {
    const databases = [
      makeDatabase("iceberg", [
        makeNamespace({
          name: "top",
          children: [
            makeSchema({ name: "t1_holder", tables: [makeTable("t1")] }),
            makeNamespace({
              name: "empty_child",
              children: [makeSchema({ name: "empty", tables: [] })],
            }),
            makeNamespace({
              name: "full_child",
              children: [
                makeSchema({ name: "full", tables: [makeTable("t2")] }),
              ],
            }),
          ],
        }),
      ]),
    ];

    expect(filterEmptyDatabases(databases)).toEqual([
      makeDatabase("iceberg", [
        makeNamespace({
          name: "top",
          children: [
            makeSchema({ name: "t1_holder", tables: [makeTable("t1")] }),
            makeNamespace({
              name: "full_child",
              children: [
                makeSchema({ name: "full", tables: [makeTable("t2")] }),
              ],
            }),
          ],
        }),
      ]),
    ]);
  });

  it("hides a parent namespace when all its descendants are empty", () => {
    const databases = [
      makeDatabase("iceberg", [
        makeNamespace({
          name: "top",
          children: [
            makeNamespace({
              name: "empty_child",
              children: [makeSchema({ name: "empty", tables: [] })],
            }),
          ],
        }),
        makeSchema({ name: "other", tables: [makeTable("t1")] }),
      ]),
    ];

    expect(filterEmptyDatabases(databases)).toEqual([
      makeDatabase("iceberg", [
        makeSchema({ name: "other", tables: [makeTable("t1")] }),
      ]),
    ]);
  });
});
