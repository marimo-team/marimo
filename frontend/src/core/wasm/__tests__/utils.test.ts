/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { shouldLoadDuckDBPackages } from "../utils";

describe("shouldLoadDuckDBPackages", () => {
  it("loads for mo.sql", () => {
    expect(shouldLoadDuckDBPackages('df = mo.sql("SELECT 1")')).toBe(true);
  });

  it("loads for detected duckdb imports and usage", () => {
    expect(shouldLoadDuckDBPackages("import duckdb")).toBe(true);
    expect(shouldLoadDuckDBPackages("from duckdb import sql")).toBe(true);
    expect(shouldLoadDuckDBPackages("rows = duckdb.sql('SELECT 1')")).toBe(
      true,
    );
  });

  it("loads when package discovery found duckdb", () => {
    expect(
      shouldLoadDuckDBPackages("print('hello')", new Set(["duckdb"])),
    ).toBe(true);
  });

  it("ignores incidental duckdb text", () => {
    expect(shouldLoadDuckDBPackages("# duckdb is mentioned here")).toBe(false);
    expect(shouldLoadDuckDBPackages("# duckdb.sql is mentioned here")).toBe(
      false,
    );
    expect(shouldLoadDuckDBPackages("name = 'duckdb'")).toBe(false);
    expect(shouldLoadDuckDBPackages("name = 'duckdb.sql'")).toBe(false);
    expect(shouldLoadDuckDBPackages('name = "duckdb.sql"')).toBe(false);
  });
});
