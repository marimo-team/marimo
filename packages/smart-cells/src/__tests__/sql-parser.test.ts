/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { parsePythonAST } from "../utils/python-ast.js";
import { SQLParser } from "../parsers/sql-parser.js";

const parser = new SQLParser();

describe("SQLParser", () => {
  describe("transformIn", () => {
    it("should extract SQL from triple double-quoted strings", () => {
      const pythonCode = '_df = mo.sql("""SELECT * FROM {df}""")';
      const { code, offset, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe("SELECT * FROM {{df}}");
      expect(metadata.dataframeName).toBe("_df");
      expect(offset).toBe(16);
    });

    it("should handle single double-quoted strings", () => {
      const pythonCode = 'next_df = mo.sql("SELECT * FROM {df}")';
      const { code, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe("SELECT * FROM {{df}}");
      expect(metadata.dataframeName).toBe("next_df");
    });

    it("should handle output flag set to True", () => {
      const pythonCode = '_df = mo.sql("""SELECT * FROM table""", output=True)';
      const { code, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe("SELECT * FROM table");
      expect(metadata.showOutput).toBe(true);
    });

    it("should handle output flag set to False", () => {
      const pythonCode =
        '_df = mo.sql("""SELECT * FROM table""", output=False)';
      const { code, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe("SELECT * FROM table");
      expect(metadata.showOutput).toBe(false);
    });

    it("should handle engine param when provided", () => {
      const pythonCode =
        '_df = mo.sql("""SELECT * FROM table""", engine=postgres_engine)';
      const { code, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe("SELECT * FROM table");
      expect(metadata.engine).toBe("postgres_engine");
    });

    it("should handle engine and output params together", () => {
      const pythonCode =
        '_df = mo.sql("""SELECT * FROM table""", output=False, engine=postgres_engine)';
      const { code, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe("SELECT * FROM table");
      expect(metadata.showOutput).toBe(false);
      expect(metadata.engine).toBe("postgres_engine");
    });

    it("should handle parametrized SQL with f-strings", () => {
      const pythonCode = `
_df = mo.sql(
    f"""
    SELECT name, price, category
    FROM products
    WHERE price < {price_threshold.value}
    ORDER BY price DESC
    """,
    engine=sqlite,
)
`;
      const { code, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe(
        `SELECT name, price, category
FROM products
WHERE price < {price_threshold.value}
ORDER BY price DESC`.trim(),
      );
      expect(metadata.engine).toBe("sqlite");
    });

    it("should handle f-strings with complex expressions containing quotes", () => {
      const pythonCode = `_df = mo.sql(
    f"""
     SELECT
        id AS idid,
        value as valval
    FROM
        sample_data
    WHERE
        id IN ({",".join(df["id"][0:2].to_list())})
    """
)`;
      const { code, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe(
        `SELECT
    id AS idid,
    value as valval
FROM
    sample_data
WHERE
    id IN ({",".join(df["id"][0:2].to_list())})`.trim(),
      );
      expect(metadata.dataframeName).toBe("_df");
    });

    it("should handle f-strings with method calls containing strings", () => {
      const pythonCode = `_df = mo.sql(f"""SELECT * FROM table WHERE col = {get_value("test")}""")`;
      const { code, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe(`SELECT * FROM table WHERE col = {get_value("test")}`);
      expect(metadata.dataframeName).toBe("_df");
    });

    it("should handle f-strings with nested brackets and quotes", () => {
      const pythonCode = `result = mo.sql(f"""
        SELECT * FROM users
        WHERE id IN ({str(data["items"][0]["id"])})
      """)`;
      const { code, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe(
        `SELECT * FROM users
WHERE id IN ({str(data["items"][0]["id"])})`.trim(),
      );
      expect(metadata.dataframeName).toBe("result");
    });

    it("should handle empty SQL string", () => {
      const pythonCode = 'next_df = mo.sql("")';
      const { code, offset } = parser.transformIn(pythonCode);
      expect(code).toBe("");
      expect(offset).toBe(18);
    });

    it("should preserve Python comments", () => {
      const pythonCode = '# hello\nmy_df = mo.sql("""SELECT * FROM {df}""")';
      const { code, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe("SELECT * FROM {{df}}");
      expect(metadata.commentLines).toEqual(["# hello"]);
    });
  });

  describe("transformOut", () => {
    it("should wrap SQL code with default settings", () => {
      const code = "SELECT * FROM {df}";
      const metadata = {
        dataframeName: "my_df",
        quotePrefix: "f" as const,
        commentLines: [],
        showOutput: true,
        engine: "__marimo_duckdb",
      };
      const { code: pythonCode } = parser.transformOut(code, metadata);
      expect(pythonCode).toMatchInlineSnapshot(`
        "my_df = mo.sql(
            f"""
            SELECT * FROM {df}
            """
        )"
      `);
    });

    it("should include output flag when set to False", () => {
      const code = "SELECT * FROM table";
      const metadata = {
        dataframeName: "my_df",
        quotePrefix: "f" as const,
        commentLines: [],
        showOutput: false,
        engine: "__marimo_duckdb",
      };
      const { code: pythonCode } = parser.transformOut(code, metadata);
      expect(pythonCode).toMatchInlineSnapshot(`
        "my_df = mo.sql(
            f"""
            SELECT * FROM table
            """,
            output=False
        )"
      `);
    });

    it("should add engine connection when provided", () => {
      const code = "SELECT * FROM table";
      const metadata = {
        dataframeName: "_df",
        quotePrefix: "f" as const,
        commentLines: ["# hello"],
        showOutput: true,
        engine: "postgres_engine",
      };
      const { code: pythonCode } = parser.transformOut(code, metadata);
      expect(pythonCode).toMatchInlineSnapshot(`
        "# hello
        _df = mo.sql(
            f"""
            SELECT * FROM table
            """,
            engine=postgres_engine
        )"
      `);
    });

    it("should add both engine and output params", () => {
      const code = "SELECT * FROM table";
      const metadata = {
        dataframeName: "_df",
        quotePrefix: "f" as const,
        commentLines: ["# hello"],
        showOutput: false,
        engine: "postgres_engine",
      };
      const { code: pythonCode } = parser.transformOut(code, metadata);
      expect(pythonCode).toMatchInlineSnapshot(`
        "# hello
        _df = mo.sql(
            f"""
            SELECT * FROM table
            """,
            output=False,
            engine=postgres_engine
        )"
      `);
    });
  });

  describe("isSupported", () => {
    it("should return true for supported formats", () => {
      const validCases = [
        'df2 = mo.sql("""SELECT * FROM {df}""")',
        "my_df = mo.sql('')",
        'df = mo.sql("")',
        '# this is a sql cell\ndf = mo.sql("")',
        '# multiple\n# comments\ndf = mo.sql("")',
        'df = mo.sql("""SELECT 1""", output=True)',
        'df = mo.sql("""SELECT 1""", engine=postgres)',
        // Complex f-string with quotes inside
        `_df = mo.sql(
    f"""
     SELECT
        id AS idid,
        value as valval
    FROM
        sample_data
    WHERE
        id IN ({",".join(df["id"][0:2].to_list())})
    """
)`,
        // F-string with method call containing string
        `_df = mo.sql(f"""SELECT * FROM table WHERE col = {get_value("test")}""")`,
        // F-string with nested brackets and quotes
        `result = mo.sql(f"""SELECT * FROM users WHERE id IN ({str(data["items"][0]["id"])})""")`,
      ];

      for (const pythonCode of validCases) {
        expect(parser.isSupported(pythonCode)).toBe(true);
      }
    });

    it("should return false for unsupported formats", () => {
      const invalidCases = [
        'print("Hello, World!")',
        "mo.sql()", // No assignment
        'mo.sql("")', // No assignment
        "_df = mo.sql()", // Empty call
        'df := mo.sql("")', // Wrong assignment operator
        // Multiple SQL calls
        'df = mo.sql("""SELECT 1""")\ndf2 = mo.sql("""SELECT 2""")',
        // Conditional expressions - issue #7386
        'df = mo.sql("""SELECT 1""") if condition else None',
        'df = mo.sql(f"""SELECT * FROM table""") if x.value else None',
        'test_df = (mo.sql(f"""SELECT * FROM table""", output=False) if true_false_widget.value else None)',
        // Binary operations
        'df = mo.sql("""SELECT 1""") or default_value',
        'df = mo.sql("""SELECT 1""") and process_it()',
      ];

      for (const pythonCode of invalidCases) {
        expect(parser.isSupported(pythonCode)).toBe(false);
      }
    });

    it("should return true for empty string", () => {
      expect(parser.isSupported("")).toBe(true);
    });

    it("should not support mo.sql() wrapped in parentheses", () => {
      // We could change this in the future if needed
      const shouldBeSupportedCases = [
        'df = (mo.sql("""SELECT 1"""))',
        'df = (\n    mo.sql("""SELECT 1""")\n)',
      ];

      for (const pythonCode of shouldBeSupportedCases) {
        expect(parser.isSupported(pythonCode)).toBe(true);
      }
    });
  });

  describe("roundtrip", () => {
    it("should roundtrip SQL correctly", () => {
      const originalSQL = "SELECT id, name FROM users WHERE active = true";
      const pythonCode = SQLParser.fromQuery(originalSQL);
      const { code, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe(originalSQL);

      const { code: backToPython } = parser.transformOut(code, metadata);
      const { code: roundtripped } = parser.transformIn(backToPython);
      expect(roundtripped).toBe(originalSQL);
    });
  });
});

describe("SQL string boundaries", () => {
  it("normalizes plain strings to f-strings without activating existing braces", () => {
    const parsed = parser.transformIn('df = mo.sql("SELECT * FROM t{1+1}")');
    expect(parsed.metadata.quotePrefix).toBe("f");
    expect(parser.transformOut(parsed.code, parsed.metadata).code).toContain(
      '\n    f"""\n',
    );
  });

  it.each(["r", "rf", "fr"])(
    "normalizes %s literals without changing Python fields",
    (prefix) => {
      const fields = prefix.includes("f") ? '{str("a\\n")}' : "{literal}";
      const parsed = parser.transformIn(
        `df = mo.sql(${prefix}"""SELECT 'a\\b' ${fields}""")`,
      );
      expect(parsed.code).toBe(
        `SELECT 'a\\\\b' ${prefix.includes("f") ? fields : "{{literal}}"}`,
      );
      expect(parsed.metadata.quotePrefix).toBe("f");
      const output = parser.transformOut(parsed.code, parsed.metadata).code;
      expect(parser.transformIn(output).code).toBe(parsed.code);
    },
  );

  it("contains quote runs for every preceding backslash parity", () => {
    for (let slashes = 0; slashes < 6; slashes++) {
      for (let quotes = 3; quotes < 13; quotes++) {
        const query = `SELECT "t${"\\".repeat(slashes)}${'"'.repeat(quotes)} + str(1+1) + "a${'"'.repeat(quotes)}`;
        const output = parser.transformOut(query, parser.defaultMetadata).code;
        const syntax = parsePythonAST(output).toString();
        expect(syntax).not.toContain("⚠");
        expect(syntax).not.toContain("BinaryExpression");
        const parsed = parser.transformIn(output);
        expect(parser.transformOut(parsed.code, parsed.metadata).code).toBe(
          output,
        );
      }
    }
  });
  it("preserves triple-quoted Python expressions inside intentional interpolation", () => {
    const query = `SELECT {"""hello""".upper()}, {value!r:>{width}}`;
    const output = parser.transformOut(query, parser.defaultMetadata).code;
    expect(output).toContain(query);
    expect(parsePythonAST(output).toString()).not.toContain("⚠");
  });

  it("does not reinterpret a protected quote run when literal braces are present", () => {
    const query = String.raw`SELECT "t{{1+1}}\""" + str(1+1) + "a"""""`;
    const output = parser.transformOut(query, parser.defaultMetadata).code;
    expect(parsePythonAST(output).toString()).not.toContain("BinaryExpression");
  });

  it.each(['SELECT "table"', 'SELECT """""""', "SELECT {value}"])(
    "contains the string boundary when constructing a cell from %s",
    (query) => {
      const code = SQLParser.fromQuery(query);
      expect(parsePythonAST(code).toString()).not.toContain("⚠");
      expect(parser.transformIn(code).code).toBe(
        parser.transformIn(
          parser.transformOut(query, parser.defaultMetadata).code,
        ).code,
      );
    },
  );

  it("preserves fields with triple quotes when SQL also contains triple single quotes", () => {
    const query = `SELECT '''sql', {"""expr""".upper()}`;
    const output = parser.transformOut(query, parser.defaultMetadata).code;
    expect(output).toContain(query);
    expect(parsePythonAST(output).toString()).not.toContain("⚠");
  });

  it.each([
    String.raw`"a\N{BULLET}{literal}"`,
    String.raw`r"a\N{BULLET}{literal}"`,
    String.raw`"a\{str(1+1)}{literal}"`,
    String.raw`"a\}{literal}"`,
  ])(
    "normalizes %s while keeping literal values and allowing new fields",
    (literal) => {
      const parsed = parser.transformIn(`df = mo.sql(${literal})`);
      expect(parsed.metadata.quotePrefix).toBe("f");
      expect(parsed.code).toContain("{{literal}}");
      const original = parser.transformOut(parsed.code, parsed.metadata).code;
      expect(parsePythonAST(original).toString()).not.toContain(
        "FormatReplacement",
      );
      const edited = parser.transformOut(
        `${parsed.code} {variable}`,
        parsed.metadata,
      ).code;
      expect(
        parsePythonAST(edited)
          .toString()
          .match(/FormatReplacement/g),
      ).toHaveLength(1);
    },
  );

  it("preserves raw format-spec literals without changing Python expressions", () => {
    const parsed = parser.transformIn(
      String.raw`df = mo.sql(rf"{str('x\n'):>{width}\n}")`,
    );
    expect(parsed.code).toBe(String.raw`{str('x\n'):>{width}\\n}`);
    expect(parsed.metadata.quotePrefix).toBe("f");
  });
});
