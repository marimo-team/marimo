/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { extractCellPreview } from "../cell-preview";

describe("extractCellPreview", () => {
  describe("markdown cells", () => {
    it("extracts heading from f-string triple-double-quoted markdown", () => {
      expect(extractCellPreview('mo.md(f"""# Heading\nbody""")')).toEqual({
        text: "# Heading",
        type: "markdown",
      });
    });

    it("extracts text from r-prefixed triple-double-quoted markdown", () => {
      expect(extractCellPreview('mo.md(r"""text""")')).toEqual({
        text: "text",
        type: "markdown",
      });
    });

    it("skips leading empty lines", () => {
      expect(extractCellPreview('mo.md(f"""\n# Heading\n""")')).toEqual({
        text: "# Heading",
        type: "markdown",
      });
    });

    it("returns undefined text for empty markdown", () => {
      expect(extractCellPreview('mo.md("")')).toEqual({
        text: undefined,
        type: "markdown",
      });
    });

    it("works with single-quoted strings", () => {
      expect(extractCellPreview("mo.md('single line')")).toEqual({
        text: "single line",
        type: "markdown",
      });
    });

    it("works with triple-single-quoted strings", () => {
      expect(extractCellPreview("mo.md('''some text''')")).toEqual({
        text: "some text",
        type: "markdown",
      });
    });

    it("works with fr prefix", () => {
      expect(extractCellPreview('mo.md(fr"""# Title\n{x}""")')).toEqual({
        text: "# Title",
        type: "markdown",
      });
    });

    it("works with no prefix", () => {
      expect(extractCellPreview('mo.md("""plain text""")')).toEqual({
        text: "plain text",
        type: "markdown",
      });
    });
  });

  describe("SQL cells", () => {
    it("extracts SQL from assignment with f-string", () => {
      expect(
        extractCellPreview('_df = mo.sql(f"""SELECT * FROM cars""")'),
      ).toEqual({
        text: "SELECT * FROM cars",
        type: "sql",
      });
    });

    it("skips leading newlines in SQL", () => {
      expect(
        extractCellPreview('_df = mo.sql(f"""\nSELECT * FROM t\n""")'),
      ).toEqual({
        text: "SELECT * FROM t",
        type: "sql",
      });
    });

    it("returns first line of multi-line SQL", () => {
      expect(
        extractCellPreview(
          '_df = mo.sql(f"""SELECT *\nFROM users\nWHERE id = 1""")',
        ),
      ).toEqual({
        text: "SELECT *",
        type: "sql",
      });
    });

    it("handles SQL with engine kwarg after string", () => {
      expect(
        extractCellPreview('_df = mo.sql(f"""SELECT 1""", engine=my_engine)'),
      ).toEqual({
        text: "SELECT 1",
        type: "sql",
      });
    });

    it("returns undefined text for empty SQL string", () => {
      expect(extractCellPreview('_df = mo.sql(f"""""")')).toEqual({
        text: undefined,
        type: "sql",
      });
    });
  });

  describe("Python fallback", () => {
    it("returns first line of Python code", () => {
      expect(extractCellPreview("import pandas as pd")).toEqual({
        text: "import pandas as pd",
        type: "python",
      });
    });

    it("returns first line of multi-line Python", () => {
      expect(extractCellPreview("x = 1\ny = 2")).toEqual({
        text: "x = 1",
        type: "python",
      });
    });

    it("returns undefined text for empty string", () => {
      // MarkdownParser.isSupported("") returns true, so empty cells
      // are classified as markdown — the text is undefined either way.
      expect(extractCellPreview("")).toEqual({
        text: undefined,
        type: "markdown",
      });
    });

    it("returns undefined text for whitespace-only string", () => {
      expect(extractCellPreview("   \n  ")).toEqual({
        text: undefined,
        type: "markdown",
      });
    });
  });
});
