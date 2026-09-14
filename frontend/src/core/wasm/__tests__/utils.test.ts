/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import {
  getNotebookSQLOutput,
  getSQLPackageNeeds,
  prependSQLPackageImports,
  shouldLoadDuckDBPackages,
} from "../utils";

describe("shouldLoadDuckDBPackages", () => {
  it("loads for mo.sql", () => {
    expect(shouldLoadDuckDBPackages('df = mo.sql("SELECT 1")')).toBe(true);
  });

  it("loads for duckdb imports and usage", () => {
    expect(shouldLoadDuckDBPackages("import duckdb")).toBe(true);
    expect(shouldLoadDuckDBPackages("from duckdb import sql")).toBe(true);
    expect(shouldLoadDuckDBPackages("import pandas, duckdb")).toBe(true);
    expect(shouldLoadDuckDBPackages("rows = duckdb.sql('SELECT 1')")).toBe(
      true,
    );
  });

  it("loads when package discovery found duckdb", () => {
    expect(
      shouldLoadDuckDBPackages("print('hello')", new Set(["duckdb"])),
    ).toBe(true);
  });

  it("does not load for incidental duckdb text", () => {
    expect(shouldLoadDuckDBPackages("name = 'duckdb'")).toBe(false);
    expect(shouldLoadDuckDBPackages("# import duckdb")).toBe(false);
  });

  it("does not load without mo.sql, duckdb usage, or discovery", () => {
    expect(shouldLoadDuckDBPackages("print('hello')")).toBe(false);
  });

  it("does not load for a Polars-only SQL cell", () => {
    expect(
      shouldLoadDuckDBPackages(
        '_df = mo.sql("SELECT * FROM orders", engine="polars")',
      ),
    ).toBe(false);
  });

  it("loads for notebooks containing both Polars and default SQL", () => {
    const code = `
polars_result = mo.sql("SELECT * FROM orders", engine="polars")
duckdb_result = mo.sql("SELECT 1")
`;
    expect(shouldLoadDuckDBPackages(code)).toBe(true);
  });
});

describe("Polars SQL package detection", () => {
  it.each([
    '_df = mo.sql("SELECT * FROM orders", engine="polars")',
    "_df = mo.sql('SELECT 1', engine = 'polars')",
    'result = marimo.sql(query="SELECT 1", engine="polars")',
    'mo.sql("SELECT 1", engine=("polars"))',
    'mo.sql("SELECT 1", engine=r"polars")',
    'mo.sql("SELECT 1", engine="""polars""")',
    'mo.sql("SELECT 1", engine="po" "lars")',
    'mo.sql("SELECT 1", engine= # selected engine\n"polars")',
  ])("loads for a static Polars engine: %s", (code) => {
    expect(getSQLPackageNeeds(code).polars).toBe(true);
  });

  it("does not load for default SQL or incidental text", () => {
    expect(getSQLPackageNeeds('df = mo.sql("SELECT 1")').polars).toBe(false);
    expect(getSQLPackageNeeds('engine = "polars"').polars).toBe(false);
    expect(
      getSQLPackageNeeds(
        `df = mo.sql("SELECT * FROM configs WHERE engine = 'polars'")`,
      ).polars,
    ).toBe(false);
  });
});

describe("Polars SQL output packages", () => {
  const polarsSQL = 'result = mo.sql("SELECT 1", engine="polars")';

  it("loads pandas and PyArrow only for pandas output", () => {
    expect(getSQLPackageNeeds(polarsSQL, { sqlOutput: "pandas" })).toEqual({
      polars: true,
      duckdb: false,
      pandasForPolars: true,
    });
    expect(getSQLPackageNeeds(polarsSQL)).toEqual({
      polars: true,
      duckdb: false,
      pandasForPolars: false,
    });
  });

  it("preloads conversion packages before an upstream Polars import", () => {
    expect(
      getSQLPackageNeeds("import polars as pl", { sqlOutput: "pandas" }),
    ).toEqual({
      polars: false,
      duckdb: false,
      pandasForPolars: true,
    });
    expect(
      getSQLPackageNeeds("import polars as pl", { sqlOutput: "auto" })
        .pandasForPolars,
    ).toBe(false);
    expect(
      prependSQLPackageImports("import polars as pl", {
        sqlOutput: "pandas",
      }),
    ).toBe("import pyarrow\nimport pandas\nimport polars as pl");
  });

  it("uses the notebook app setting over the user default", () => {
    const code = `
app = marimo.App(sql_output="native")
${polarsSQL}
`;
    expect(getNotebookSQLOutput(code, "pandas")).toBe("native");
    expect(
      getSQLPackageNeeds(code, { sqlOutput: "pandas" }).pandasForPolars,
    ).toBe(false);
  });

  it("recognizes a pandas notebook app setting", () => {
    const code = `
app = marimo.App(sql_output="pandas")
${polarsSQL}
`;
    expect(getSQLPackageNeeds(code).pandasForPolars).toBe(true);
  });

  it("builds one ordered import prelude for mixed SQL engines", () => {
    const code =
      'result = mo.sql("SELECT 1", engine="po" "lars")\n' +
      'result2 = mo.sql("SELECT 2")';

    expect(prependSQLPackageImports(code, { sqlOutput: "auto" })).toBe(
      `import pyarrow\nimport sqlglot\nimport duckdb\nimport pandas\nimport polars\n${code}`,
    );
  });
});
