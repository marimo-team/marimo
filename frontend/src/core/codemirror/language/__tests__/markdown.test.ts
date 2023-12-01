/* Copyright 2023 Marimo. All rights reserved. */
import { expect, describe, it } from "vitest";
import { MarkdownLanguageAdapter } from "../markdown";

const adapter = new MarkdownLanguageAdapter();

describe("MarkdownLanguageAdapter", () => {
  describe("transformIn", () => {
    it("should extract inner Markdown from triple double-quoted strings", () => {
      const pythonCode = 'mo.md("""# Markdown Title\n\nSome content here.""")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("# Markdown Title\n\nSome content here.");
      expect(offset).toBe(9);
    });

    it("should handle single double-quoted strings", () => {
      const pythonCode = 'mo.md("Some *markdown* content")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("Some *markdown* content");
      expect(offset).toBe(7);
    });

    it("should handle triple single-quoted strings", () => {
      const pythonCode = "mo.md('''# Another Title\nContent''')";
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("# Another Title\nContent");
      expect(offset).toBe(9);
    });

    it("should throw if no markdown is detected", () => {
      const pythonCode = 'print("Hello, World!")';
      expect(() =>
        adapter.transformIn(pythonCode)
      ).toThrowErrorMatchingInlineSnapshot('"Not supported"');
    });

    it("should handle an empty string", () => {
      const pythonCode = 'mo.md("")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("");
      expect(offset).toBe(0);
    });

    it("should unescape code blocks", () => {
      // f"""
      const pythonCode = 'mo.md(f"""This is some \\"""content\\"""!""")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(`This is some """content"""!`);
      expect(offset).toBe(10);

      // """
      const pythonCode2 = 'mo.md("""This is some \\"""content\\"""!""")';
      const [innerCode2, offset2] = adapter.transformIn(pythonCode2);
      expect(innerCode2).toBe(`This is some """content"""!`);
      expect(offset2).toBe(9);

      // "
      const pythonCode3 = 'mo.md("This is some \\"content\\"!")';
      const [innerCode3, offset3] = adapter.transformIn(pythonCode3);
      expect(innerCode3).toBe(`This is some "content"!`);
      expect(offset3).toBe(7);

      // '
      const pythonCode4 = "mo.md('This is some \\'content\\'!')";
      const [innerCode4, offset4] = adapter.transformIn(pythonCode4);
      expect(innerCode4).toBe(`This is some 'content'!`);
      expect(offset4).toBe(7);
    });

    it("should handle strings with escaped quotes", () => {
      const pythonCode = 'mo.md("""Markdown with an escaped \\"quote\\"""")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe('Markdown with an escaped \\"quote\\"');
      expect(offset).toBe('mo.md("""'.length);
    });

    it("should handle strings with nested markdown", () => {
      const pythonCode =
        'mo.md("""# Title\n\n```python\nprint("Hello, Markdown!")\n```""")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(
        '# Title\n\n```python\nprint("Hello, Markdown!")\n```'
      );
      expect(offset).toBe('mo.md("""'.length);
    });

    it("should return the original string if no markdown delimiters are present", () => {
      const pythonCode = 'print("No markdown here")';
      expect(() =>
        adapter.transformIn(pythonCode)
      ).toThrowErrorMatchingInlineSnapshot('"Not supported"');
    });

    it("should handle multiple markdown blocks in a single string", () => {
      const pythonCode =
        'mo.md("""# Title 1""") + "\\n" + mo.md("""## Title 2""")';
      expect(() =>
        adapter.transformIn(pythonCode)
      ).toThrowErrorMatchingInlineSnapshot('"Not supported"');
    });

    it("simple markdown", () => {
      const pythonCode = 'mo.md("# Title without proper delimiters")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("# Title without proper delimiters");
      expect(offset).toBe(7);
    });

    it("should handle strings with leading and trailing whitespace", () => {
      const pythonCode = 'mo.md("""   \n# Title\nContent\n   """)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("   \n# Title\nContent\n   ");
      expect(offset).toBe(9);
    });

    it("should handle space around the f=strings", () => {
      const pythonCode = 'mo.md(\n\t"""\n# Title\nContent\n"""\n)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("\n# Title\nContent\n");
      expect(offset).toBe(11);
    });
  });

  describe("transformOut", () => {
    it("should wrap Markdown code with triple double-quoted string format", () => {
      const code = "# Markdown Title\n\nSome content here.";
      const [wrappedCode, offset] = adapter.transformOut(code);
      expect(wrappedCode).toBe(`mo.md(f"""${code}""")`);
      expect(offset).toBe(10);
    });

    it("should escape triple quotes in the Markdown code", () => {
      const code = 'Markdown with an escaped """quote"""!!';
      const [wrappedCode, offset] = adapter.transformOut(code);
      expect(wrappedCode).toBe(
        `mo.md(f"""Markdown with an escaped \\"""quote\\"""!!""")`
      );
      expect(offset).toBe(10);
    });
  });

  describe("isSupported", () => {
    it("should return true for supported markdown string formats", () => {
      const pythonCode = 'mo.md("""# Markdown Title\n\nSome content here.""")';
      expect(adapter.isSupported(pythonCode)).toBe(true);
    });

    it("should return false for unsupported string formats", () => {
      const pythonCode = 'print("Hello, World!")';
      expect(adapter.isSupported(pythonCode)).toBe(false);
    });
  });
});
