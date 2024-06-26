/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, it } from "vitest";
import { SQLLanguageAdapter } from "../sql";

const adapter = new SQLLanguageAdapter();

describe("SQLLanguageAdapter", () => {
  describe("transformIn", () => {
    it("should extract inner SQL from triple double-quoted strings", () => {
      const pythonCode = 'mo.sql("""select * from {df}""")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("select * from {df}");
      expect(offset).toBe(10);
    });

    it("should handle single double-quoted strings", () => {
      const pythonCode = 'mo.sql("select * from {df}")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("select * from {df}");
      expect(offset).toBe(8);
    });

    it("should handle triple single-quoted strings", () => {
      const pythonCode = "mo.sql('''select * \nfrom {df}''')";
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("select * \nfrom {df}");
      expect(offset).toBe(10);
    });

    it("should throw if no sql is detected", () => {
      const pythonCode = 'print("Hello, World!")';
      expect(() =>
        adapter.transformIn(pythonCode),
      ).toThrowErrorMatchingInlineSnapshot(`[Error: Not supported]`);
    });

    it("should handle an empty string", () => {
      const pythonCode = 'mo.sql("")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("");
      expect(offset).toBe(0);
    });

    it("simple sql", () => {
      const pythonCode = 'mo.sql("select * from {df}")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("select * from {df}");
      expect(offset).toBe(8);
    });

    it("should trim strings with leading and trailing whitespace", () => {
      const pythonCode = 'mo.sql("""   \nselect * from {df}\n   """)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("select * from {df}");
      expect(offset).toBe(10);
    });

    it("should handle space around the f-strings", () => {
      const pythonCode = 'mo.sql(\n\t"""\nselect * from {df}\n"""\n)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("select * from {df}");
      expect(offset).toBe(12);
    });
  });

  describe("transformOut", () => {
    it("should wrap SQL code with triple double-quoted string format", () => {
      const code = "select * from {df}";
      adapter.lastQuotePrefix = "";
      const [wrappedCode, offset] = adapter.transformOut(code);
      expect(wrappedCode).toMatchInlineSnapshot(`
        "mo.sql(
            f"""
            select * from {df}
            """
        )"
      `);
      expect(offset).toBe(18);
    });
  });

  describe("isSupported", () => {
    it("should return true for supported sql string formats", () => {
      const pythonCode = 'mo.sql("""select * from {df}""")';
      expect(adapter.isSupported(pythonCode)).toBe(true);
      expect(adapter.isSupported("mo.sql()")).toBe(true);
      expect(adapter.isSupported("mo.sql('')")).toBe(true);
      expect(adapter.isSupported('mo.sql("")')).toBe(true);
    });

    it("should return false for unsupported string formats", () => {
      const pythonCode = 'print("Hello, World!")';
      expect(adapter.isSupported(pythonCode)).toBe(false);
    });

    it("should return false sequences that look like sql but are not", () => {
      const once = 'mo.sql("""select * from {df}""")';
      const pythonCode = [once, once].join("\n");
      expect(adapter.isSupported(pythonCode)).toBe(false);
    });
  });
});
