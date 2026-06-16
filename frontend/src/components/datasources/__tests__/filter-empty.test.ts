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

// `tables`/`children` default to `[]` (discovered and empty). Pass `null` to
// model a deferred bucket that has not been discovered yet.
function makeSchema({
  name,
  tables = [],
}: {
  name: string;
  tables?: DataTable[] | null;
}): DatabaseSchema {
  return { kind: "schema", name, tables };
}

function makeNamespace({
  name,
  children = [],
}: {
  name: string;
  children?: CatalogNode[] | null;
}): DatabaseNamespace {
  return { kind: "namespace", name, children };
}

function makeDatabase(name: string, children: CatalogNode[] | null): Database {
  return {
    name,
    dialect: "duckdb",
    children,
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

  it("preserves databases whose children have not been resolved yet (deferred)", () => {
    const databases = [makeDatabase("not_loaded_yet", null)];

    expect(filterEmptyDatabases(databases)).toEqual([
      makeDatabase("not_loaded_yet", null),
    ]);
  });

  it("hides databases that have been resolved as empty", () => {
    const databases = [
      makeDatabase("really_empty", []),
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

  it("preserves schemas whose tables have not been loaded yet", () => {
    const databases = [
      makeDatabase("snowflake_db", [
        makeSchema({ name: "public", tables: null }),
        makeSchema({ name: "audit", tables: null }),
        makeSchema({ name: "really_empty", tables: [] }),
      ]),
    ];

    expect(filterEmptyDatabases(databases)).toEqual([
      makeDatabase("snowflake_db", [
        makeSchema({ name: "public", tables: null }),
        makeSchema({ name: "audit", tables: null }),
      ]),
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
          children: null,
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
