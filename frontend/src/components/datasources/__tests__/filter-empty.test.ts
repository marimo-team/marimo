/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import {
  type CatalogNode,
  catalogNodePath,
  isNamespaceNode,
  isSchemaNode,
} from "@/core/datasets/catalog";
import {
  type CatalogLoadState,
  catalogPathKey,
  emptyCatalogLoadState,
} from "@/core/datasets/catalog-load-state";
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
}): DatabaseSchema {
  return {
    kind: "schema",
    name: opts.name,
    tables: opts.tables,
  };
}

function makeNamespace(opts: {
  name: string;
  children?: CatalogNode[];
}): DatabaseNamespace {
  return {
    kind: "namespace",
    name: opts.name,
    children: opts.children ?? [],
  };
}

function makeDatabase(name: string, children: CatalogNode[]): Database {
  return {
    name,
    dialect: "duckdb",
    children,
    engine: null,
  };
}

function fullyLoaded(databases: Database[]): CatalogLoadState {
  const childrenLoaded = new Set<string>();
  const tablesLoaded = new Set<string>();

  const visit = (
    database: string,
    nodes: CatalogNode[],
    path: string[],
  ): void => {
    childrenLoaded.add(catalogPathKey(database, path));

    for (const node of nodes) {
      if (isSchemaNode(node)) {
        tablesLoaded.add(
          catalogPathKey(
            database,
            catalogNodePath({ schema: node.name, schemaPath: path }),
          ),
        );
        continue;
      }
      if (isNamespaceNode(node)) {
        const namespacePath = [...path, node.name];
        childrenLoaded.add(catalogPathKey(database, namespacePath));
        tablesLoaded.add(catalogPathKey(database, namespacePath));
        visit(database, node.children, namespacePath);
      }
    }
  };

  for (const database of databases) {
    visit(database.name, database.children, []);
  }

  return { childrenLoaded, tablesLoaded };
}

function filterLoaded(databases: Database[]): Database[] {
  return filterEmptyDatabases({
    databases,
    catalogLoad: fullyLoaded(databases),
  });
}

describe("filterEmptyDatabases", () => {
  it("hides schemas whose tables are resolved and empty", () => {
    const databases = [
      makeDatabase("memory", [
        makeSchema({ name: "main", tables: [makeTable("t1")] }),
        makeSchema({ name: "empty_schema", tables: [] }),
      ]),
    ];

    expect(filterLoaded(databases)).toEqual([
      makeDatabase("memory", [
        makeSchema({ name: "main", tables: [makeTable("t1")] }),
      ]),
    ]);
  });

  it("preserves databases whose children have not been resolved yet (lazy state)", () => {
    const databases = [makeDatabase("not_loaded_yet", [])];

    expect(
      filterEmptyDatabases({
        databases,
        catalogLoad: emptyCatalogLoadState(),
      }),
    ).toEqual([makeDatabase("not_loaded_yet", [])]);
  });

  it("hides databases that have been resolved as empty", () => {
    const databases = [
      makeDatabase("really_empty", []),
      makeDatabase("has_tables", [
        makeSchema({ name: "main", tables: [makeTable("t1")] }),
      ]),
    ];

    expect(filterLoaded(databases)).toEqual([
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

    expect(filterLoaded(databases)).toEqual([
      makeDatabase("has_tables", [
        makeSchema({ name: "main", tables: [makeTable("t1")] }),
      ]),
    ]);
  });

  it("preserves schemas whose tables have not been loaded yet", () => {
    const databases = [
      makeDatabase("snowflake_db", [
        makeSchema({ name: "public", tables: [] }),
        makeSchema({ name: "audit", tables: [] }),
        makeSchema({ name: "really_empty", tables: [] }),
      ]),
    ];
    const load = {
      ...emptyCatalogLoadState(),
      childrenLoaded: new Set([catalogPathKey("snowflake_db", [])]),
      tablesLoaded: new Set([catalogPathKey("snowflake_db", ["really_empty"])]),
    };

    expect(filterEmptyDatabases({ databases, catalogLoad: load })).toEqual([
      makeDatabase("snowflake_db", [
        makeSchema({ name: "public", tables: [] }),
        makeSchema({ name: "audit", tables: [] }),
      ]),
    ]);
  });

  it("returns the same reference when nothing was filtered", () => {
    const databases = [
      makeDatabase("memory", [
        makeSchema({ name: "main", tables: [makeTable("t1")] }),
      ]),
    ];

    expect(filterLoaded(databases)).toBe(databases);
  });

  it("does not mutate the input", () => {
    const databases = [
      makeDatabase("memory", [
        makeSchema({ name: "main", tables: [makeTable("t1")] }),
        makeSchema({ name: "empty_schema", tables: [] }),
      ]),
    ];
    const snapshot = JSON.parse(JSON.stringify(databases));

    filterLoaded(databases);

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

    expect(filterLoaded(databases)).toBe(databases);
  });

  it("preserves a namespace whose children are deferred", () => {
    const databases = [
      makeDatabase("iceberg", [
        makeNamespace({
          name: "top",
          children: [],
        }),
      ]),
    ];

    expect(
      filterEmptyDatabases({
        databases,
        catalogLoad: emptyCatalogLoadState(),
      }),
    ).toBe(databases);
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

    expect(filterLoaded(databases)).toEqual([
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

    expect(filterLoaded(databases)).toEqual([
      makeDatabase("iceberg", [
        makeSchema({ name: "other", tables: [makeTable("t1")] }),
      ]),
    ]);
  });
});
