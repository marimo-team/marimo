/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import {
  mergeTableAtPath,
  setTablesAtPath,
  walkCatalogNodes,
} from "../catalog";
import { databaseWithSchemas, makeTable } from "./catalog-fixtures";

describe("walkCatalogNodes", () => {
  it("uses container segments for inline data tables in namespaces", () => {
    const table = makeTable("orders", {
      source: "iceberg",
      source_type: "catalog",
    });
    const database = {
      ...databaseWithSchemas("top", "iceberg", []),
      children: [
        {
          kind: "namespace" as const,
          name: "nested",
          children: [table],
          children_resolved: true,
          tables_resolved: true,
        },
      ],
    };

    const paths: string[][] = [];
    walkCatalogNodes(
      database.children,
      { databaseName: database.name, segments: [] },
      ({ node, segments }) => {
        if (node.kind === "data_table") {
          paths.push([...segments]);
        }
      },
    );

    expect(paths).toEqual([["nested"]]);
  });
});

describe("mergeTableAtPath", () => {
  it("appends a new table when the schema already has other tables", () => {
    const existing = makeTable("a");
    const incoming = makeTable("b");
    const children = databaseWithSchemas("db", "duckdb", [
      { name: "public", tables: [existing] },
    ]).children;

    const updated = mergeTableAtPath(children, ["public"], incoming);
    const schema = updated.find((node) => node.kind === "schema");
    expect(schema?.kind).toBe("schema");
    if (schema?.kind !== "schema") {
      return;
    }
    expect(schema.tables.map((table) => table.name)).toEqual(["a", "b"]);
  });
});

describe("setTablesAtPath", () => {
  it("replaces the full table list at a schema path", () => {
    const children = databaseWithSchemas("db", "duckdb", [
      { name: "public", tables: [makeTable("old")] },
    ]).children;
    const replacement = [makeTable("new")];

    const updated = setTablesAtPath(children, ["public"], replacement);
    const schema = updated.find((node) => node.kind === "schema");
    expect(schema?.kind).toBe("schema");
    if (schema?.kind !== "schema") {
      return;
    }
    expect(schema.tables).toEqual(replacement);
  });
});
