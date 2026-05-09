/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { shouldLoadDuckDBPackages } from "../utils";

describe("shouldLoadDuckDBPackages", () => {
  it("loads for mo.sql", () => {
    expect(shouldLoadDuckDBPackages('df = mo.sql("SELECT 1")')).toBe(true);
  });

  it("loads for duckdb text", () => {
    expect(shouldLoadDuckDBPackages("import duckdb")).toBe(true);
    expect(shouldLoadDuckDBPackages("from duckdb import sql")).toBe(true);
    expect(shouldLoadDuckDBPackages("import pandas, duckdb")).toBe(true);
    expect(shouldLoadDuckDBPackages("rows = duckdb.sql('SELECT 1')")).toBe(
      true,
    );
    expect(shouldLoadDuckDBPackages("name = 'duckdb'")).toBe(true);
  });

  it("loads when package discovery found duckdb", () => {
    expect(
      shouldLoadDuckDBPackages("print('hello')", new Set(["duckdb"])),
    ).toBe(true);
  });

  it("does not load without mo.sql, duckdb text, or discovery", () => {
    expect(shouldLoadDuckDBPackages("print('hello')")).toBe(false);
  });
});
