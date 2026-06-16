/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { DatabaseNamespace } from "@/core/kernel/messages";
import type { CatalogNode } from "../catalog";
import {
  catalogChildrenMatchSearch,
  catalogNodePath,
  catalogSubtreeMatchesSearch,
  findNodeAtPath,
  mergeTableAtPath,
  setCatalogChildrenAtPath,
  shouldExpandCatalogNodeForSearch,
  shouldExpandDatabaseForSearch,
  walkCatalogNodes,
} from "../catalog";
import { databaseWithSchemas, makeSchema, makeTable } from "./catalog-fixtures";

function makeNamespace(name: string, children: CatalogNode[]): CatalogNode {
  return { kind: "namespace", name, children };
}

describe("catalogNodePath", () => {
  it("uses the schema name for top-level schemas", () => {
    expect(catalogNodePath({ schema: "public" })).toEqual(["public"]);
  });

  it("returns an empty path for database-level tables", () => {
    expect(catalogNodePath({ schema: "" })).toEqual([]);
  });

  it("appends the schema name to a parent namespace path", () => {
    expect(catalogNodePath({ schema: "nested", catalogPath: ["top"] })).toEqual(
      ["top", "nested"],
    );
  });

  it("does not duplicate the leaf schema when catalogPath is already complete", () => {
    expect(
      catalogNodePath({
        schema: "nested",
        catalogPath: ["top", "nested"],
      }),
    ).toEqual(["top", "nested"]);
  });
});

describe("walkCatalogNodes", () => {
  it("uses container segments for inline data tables in namespaces", () => {
    const table = makeTable("orders", {
      source: "iceberg",
      source_type: "catalog",
    });
    const database = {
      ...databaseWithSchemas({
        name: "top",
        dialect: "iceberg",
        schemas: [],
      }),
      children: [
        {
          kind: "namespace" as const,
          name: "nested",
          children: [table],
        },
      ],
    };

    const paths: string[][] = [];
    walkCatalogNodes({
      nodes: database.children,
      context: { databaseName: database.name, segments: [] },
      visit: ({ node, segments }) => {
        if (node.kind === "data_table") {
          paths.push([...segments]);
        }
      },
    });

    expect(paths).toEqual([["nested"]]);
  });
});

describe("mergeTableAtPath", () => {
  it("appends a new table when the schema already has other tables", () => {
    const existing = makeTable("a");
    const incoming = makeTable("b");
    const children = databaseWithSchemas({
      name: "db",
      dialect: "duckdb",
      schemas: [{ name: "public", tables: [existing] }],
    }).children;

    const updated = mergeTableAtPath({
      nodes: children ?? [],
      path: ["public"],
      table: incoming,
    });
    const schema = updated.find((node) => node.kind === "schema");
    expect(schema?.kind).toBe("schema");
    if (schema?.kind !== "schema") {
      return;
    }
    expect((schema.tables ?? []).map((table) => table.name)).toEqual([
      "a",
      "b",
    ]);
  });

  it("merges a table into a schema nested under a namespace", () => {
    const nodes: CatalogNode[] = [
      makeNamespace("nested", [makeSchema("deep", [makeTable("a")])]),
    ];

    const updated = mergeTableAtPath({
      nodes,
      path: ["nested", "deep"],
      table: makeTable("b"),
    });

    const schema = findNodeAtPath({ nodes: updated, path: ["nested", "deep"] });
    expect(schema?.kind).toBe("schema");
    if (schema?.kind !== "schema") {
      return;
    }
    expect((schema.tables ?? []).map((table) => table.name)).toEqual([
      "a",
      "b",
    ]);
  });

  it("upserts a table by name at a nested path (replaces, not duplicates)", () => {
    const nodes: CatalogNode[] = [
      makeNamespace("nested", [
        makeSchema("deep", [makeTable("orders", { num_rows: 1 })]),
      ]),
    ];

    const updated = mergeTableAtPath({
      nodes,
      path: ["nested", "deep"],
      table: makeTable("orders", { num_rows: 42 }),
    });

    const schema = findNodeAtPath({ nodes: updated, path: ["nested", "deep"] });
    if (schema?.kind !== "schema") {
      throw new Error("expected schema node");
    }
    expect(schema.tables).toEqual([makeTable("orders", { num_rows: 42 })]);
  });

  it("merges an inline table directly into a namespace", () => {
    const nodes: CatalogNode[] = [
      makeNamespace("nested", [makeSchema("deep", [makeTable("a")])]),
    ];

    const updated = mergeTableAtPath({
      nodes,
      path: ["nested"],
      table: makeTable("inline"),
    });

    const namespace = findNodeAtPath({ nodes: updated, path: ["nested"] });
    if (namespace?.kind !== "namespace") {
      throw new Error("expected namespace node");
    }
    // The existing schema child is preserved alongside the new inline table.
    expect((namespace.children ?? []).map((node) => node.name)).toEqual([
      "deep",
      "inline",
    ]);
  });
});

describe("setCatalogChildrenAtPath", () => {
  it("replaces table children at a schema path", () => {
    const children = databaseWithSchemas({
      name: "db",
      dialect: "duckdb",
      schemas: [{ name: "public", tables: [makeTable("old")] }],
    }).children;
    const replacement = [makeTable("new")];

    const updated = setCatalogChildrenAtPath({
      nodes: children ?? [],
      path: ["public"],
      children: replacement,
    });
    const schema = updated.find((node) => node.kind === "schema");
    expect(schema?.kind).toBe("schema");
    if (schema?.kind !== "schema") {
      return;
    }
    expect(schema.tables).toEqual(replacement);
  });

  it("replaces a nested namespace's children, resolving its deferred bucket", () => {
    const nodes: CatalogNode[] = [
      makeNamespace("top", [
        { kind: "namespace", name: "child", children: null },
      ]),
    ];
    const replacement: CatalogNode[] = [makeSchema("deep", [makeTable("t1")])];

    const updated = setCatalogChildrenAtPath({
      nodes,
      path: ["top", "child"],
      children: replacement,
    });

    const namespace = findNodeAtPath({
      nodes: updated,
      path: ["top", "child"],
    });
    if (namespace?.kind !== "namespace") {
      throw new Error("expected namespace node");
    }
    expect(namespace.children).toEqual(replacement);
  });
});

describe("catalogSubtreeMatchesSearch", () => {
  it("matches a table in a resolved schema", () => {
    const schema = makeSchema("public", [makeTable("orders")]);
    expect(catalogSubtreeMatchesSearch(schema, "ord")).toBe(true);
    expect(catalogSubtreeMatchesSearch(schema, "missing")).toBe(false);
  });

  it("returns false when schema tables are deferred", () => {
    const schema: CatalogNode = {
      kind: "schema",
      name: "public",
      tables: null,
    };
    expect(catalogSubtreeMatchesSearch(schema, "anything")).toBe(false);
  });

  it("matches nested resolved namespaces", () => {
    const node = makeNamespace("top", [
      makeNamespace("nested", [makeSchema("deep", [makeTable("target")])]),
    ]);
    expect(catalogSubtreeMatchesSearch(node, "target")).toBe(true);
    expect(catalogSubtreeMatchesSearch(node, "other")).toBe(false);
  });

  it("returns false when a namespace child bucket is deferred", () => {
    const node: CatalogNode = {
      kind: "namespace",
      name: "top",
      children: null,
    };
    expect(catalogSubtreeMatchesSearch(node, "target")).toBe(false);
  });

  it("matches inline tables on a namespace", () => {
    const node = makeNamespace("top", [makeTable("inline_table")]);
    expect(catalogSubtreeMatchesSearch(node, "inline")).toBe(true);
  });
});

describe("shouldExpandCatalogNodeForSearch", () => {
  it("does not expand deferred namespaces", () => {
    const node: CatalogNode = {
      kind: "namespace",
      name: "top",
      children: null,
    };
    expect(
      shouldExpandCatalogNodeForSearch(node as DatabaseNamespace, "anything"),
    ).toBe(false);
  });

  it("expands resolved namespaces with a matching descendant", () => {
    const node = makeNamespace("top", [
      makeSchema("main", [makeTable("users")]),
    ]);
    expect(
      shouldExpandCatalogNodeForSearch(node as DatabaseNamespace, "user"),
    ).toBe(true);
  });
});

describe("shouldExpandDatabaseForSearch", () => {
  it("does not expand when database children are deferred", () => {
    expect(shouldExpandDatabaseForSearch(null, "users")).toBe(false);
  });

  it("expands when resolved children contain a match", () => {
    const children = [makeSchema("main", [makeTable("users")])];
    expect(shouldExpandDatabaseForSearch(children, "user")).toBe(true);
    expect(shouldExpandDatabaseForSearch(children, "missing")).toBe(false);
  });
});

describe("catalogChildrenMatchSearch", () => {
  it("searches across multiple top-level nodes", () => {
    const children = [
      makeSchema("empty", []),
      makeSchema("main", [makeTable("orders")]),
    ];
    expect(catalogChildrenMatchSearch(children, "orders")).toBe(true);
    expect(catalogChildrenMatchSearch(children, "nope")).toBe(false);
  });
});
