/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import {
  catalogNodePath,
  mergeTableAtPath,
  setCatalogChildrenAtPath,
  walkCatalogNodes,
} from "../catalog";
import { databaseWithSchemas, makeTable } from "./catalog-fixtures";

describe("catalogNodePath", () => {
  it("uses the schema name for top-level schemas", () => {
    expect(catalogNodePath({ schema: "public" })).toEqual(["public"]);
  });

  it("returns an empty path for database-level tables", () => {
    expect(catalogNodePath({ schema: "" })).toEqual([]);
  });

  it("appends the schema name to a parent namespace path", () => {
    expect(catalogNodePath({ schema: "nested", schemaPath: ["top"] })).toEqual([
      "top",
      "nested",
    ]);
  });

  it("does not duplicate the leaf schema when schemaPath is already complete", () => {
    expect(
      catalogNodePath({
        schema: "nested",
        schemaPath: ["top", "nested"],
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
      nodes: children,
      path: ["public"],
      table: incoming,
    });
    const schema = updated.find((node) => node.kind === "schema");
    expect(schema?.kind).toBe("schema");
    if (schema?.kind !== "schema") {
      return;
    }
    expect(schema.tables.map((table) => table.name)).toEqual(["a", "b"]);
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
      nodes: children,
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
});
