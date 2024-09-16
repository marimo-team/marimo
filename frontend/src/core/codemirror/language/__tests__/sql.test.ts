/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it, beforeAll } from "vitest";
import { SQLLanguageAdapter } from "../sql";
import { store } from "@/core/state/jotai";
import { capabilitiesAtom } from "@/core/config/capabilities";

const adapter = new SQLLanguageAdapter();

describe("SQLLanguageAdapter", () => {
  beforeAll(() => {
    store.set(capabilitiesAtom, {
      sql: true,
      terminal: true,
    });
  });

  describe("transformIn", () => {
    it("empty", () => {
      const [innerCode, offset] = adapter.transformIn("");
      expect(innerCode).toBe("");
      expect(offset).toBe(0);
      const out = adapter.transformOut(innerCode);
      expect(out).toMatchInlineSnapshot(`
        [
          "_df = mo.sql(
            f"""

            """
        )",
          24,
        ]
      `);
    });

    it("should extract inner SQL from triple double-quoted strings", () => {
      const pythonCode = '_df = mo.sql("""SELECT * FROM {df}""")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM {df}");
      expect(adapter.dataframeName).toBe("_df");
      expect(offset).toBe(16);
    });

    it("should handle single double-quoted strings", () => {
      const pythonCode = 'next_df = mo.sql("SELECT * FROM {df}")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM {df}");
      expect(adapter.dataframeName).toBe("next_df");
      expect(offset).toBe(18);
    });

    it("should handle triple single-quoted strings", () => {
      const pythonCode = "next_df = mo.sql('''SELECT * \nFROM {df}''')";
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * \nFROM {df}");
      expect(offset).toBe(20);
    });

    it("should throw if no sql is detected", () => {
      const pythonCode = 'next_df = print("Hello, World!")';
      expect(() =>
        adapter.transformIn(pythonCode),
      ).toThrowErrorMatchingInlineSnapshot("[Error: Not supported]");
    });

    it("should handle an empty string", () => {
      const pythonCode = 'next_df = mo.sql("")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("");
      expect(offset).toBe(0);
    });

    it("simple sql", () => {
      const pythonCode = 'next_df = mo.sql("SELECT * FROM {df}")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM {df}");
      expect(offset).toBe(18);
    });

    it("should trim strings with leading and trailing whitespace", () => {
      const pythonCode = 'next_df = mo.sql("""   \nSELECT * FROM {df}\n   """)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM {df}");
      expect(offset).toBe(20);
    });

    it("should handle space around the f-strings", () => {
      const pythonCode = 'next_df = mo.sql(\n\t"""\nSELECT * FROM {df}\n"""\n)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM {df}");
      expect(offset).toBe(22);
    });

    it("should handle output flag set to True", () => {
      const pythonCode = '_df = mo.sql("""SELECT * FROM table""", output=True)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM table");
      expect(adapter.showOutput).toBe(true);
      expect(offset).toBe(16);
    });

    it("should handle output flag set to False", () => {
      const pythonCode =
        '_df = mo.sql("""SELECT * FROM table""", output=False)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("SELECT * FROM table");
      expect(adapter.showOutput).toBe(false);
      expect(offset).toBe(16);
    });

    it("should default to showing output when flag is not specified", () => {
      const pythonCode = '_df = mo.sql("""SELECT * FROM table""")';
      adapter.transformIn(pythonCode);
      expect(adapter.showOutput).toBe(true);
    });
  });

  describe("transformOut", () => {
    it("should wrap SQL code with triple double-quoted string format", () => {
      const code = "SELECT * FROM {df}";
      adapter.lastQuotePrefix = "";
      adapter.dataframeName = "my_df";
      const [wrappedCode, offset] = adapter.transformOut(code);
      expect(wrappedCode).toMatchInlineSnapshot(`
        "my_df = mo.sql(
            f"""
            SELECT * FROM {df}
            """
        )"
      `);
      expect(offset).toBe(26);
    });

    it("should include output flag when set to False", () => {
      const code = "SELECT * FROM table";
      adapter.lastQuotePrefix = "f";
      adapter.dataframeName = "my_df";
      adapter.showOutput = false;
      const [wrappedCode, offset] = adapter.transformOut(code);
      expect(wrappedCode).toMatchInlineSnapshot(`
        "my_df = mo.sql(
            f"""
            SELECT * FROM table
            """, output=False
        )"
      `);
      expect(offset).toBe(26);
    });

    it("should not include output flag when set to True", () => {
      const code = "SELECT * FROM table";
      adapter.lastQuotePrefix = "f";
      adapter.dataframeName = "my_df";
      adapter.showOutput = true;
      const [wrappedCode, offset] = adapter.transformOut(code);
      expect(wrappedCode).toMatchInlineSnapshot(`
        "my_df = mo.sql(
            f"""
            SELECT * FROM table
            """
        )"
      `);
      expect(offset).toBe(26);
    });
  });

  describe("isSupported", () => {
    it("should return true for supported sql string formats", () => {
      expect(
        adapter.isSupported('df2 = mo.sql("""SELECT * FROM {df}""")'),
      ).toBe(true);
      expect(adapter.isSupported("my_df = mo.sql('')")).toBe(true);
      expect(adapter.isSupported('df = mo.sql("")')).toBe(true);
      expect(adapter.isSupported(new SQLLanguageAdapter().defaultCode)).toBe(
        true,
      );
    });

    it("should return false for unsupported string formats", () => {
      expect(adapter.isSupported('print("Hello, World!")')).toBe(false);
      expect(adapter.isSupported("mo.sql()")).toBe(false);
      expect(adapter.isSupported("mo.sql('')")).toBe(false);
      expect(adapter.isSupported('mo.sql("")')).toBe(false);
      expect(adapter.isSupported("_df = mo.sql()")).toBe(false);
      expect(adapter.isSupported('df := mo.sql("")')).toBe(false);
    });

    it("should return false sequences that look like sql but are not", () => {
      const once = 'df = mo.sql("""SELECT * FROM {df}""")';
      const pythonCode = [once, once].join("\n");
      expect(adapter.isSupported(pythonCode)).toBe(false);
    });

    it("should support SQL strings with output flag", () => {
      expect(
        adapter.isSupported(
          'df = mo.sql("""SELECT * FROM table""", output=True)',
        ),
      ).toBe(true);
      expect(
        adapter.isSupported(
          'df = mo.sql("""SELECT * FROM table""", output=False)',
        ),
      ).toBe(true);
    });
  });
});
