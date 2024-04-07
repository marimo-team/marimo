/* Copyright 2024 Marimo. All rights reserved. */
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
        adapter.transformIn(pythonCode),
      ).toThrowErrorMatchingInlineSnapshot(`[Error: Not supported]`);
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
        '# Title\n\n```python\nprint("Hello, Markdown!")\n```',
      );
      expect(offset).toBe('mo.md("""'.length);
    });

    it("should return the original string if no markdown delimiters are present", () => {
      const pythonCode = 'print("No markdown here")';
      expect(() =>
        adapter.transformIn(pythonCode),
      ).toThrowErrorMatchingInlineSnapshot(`[Error: Not supported]`);
    });

    it("should handle multiple markdown blocks in a single string", () => {
      const pythonCode = `mo.md("""
        # Hello, Markdown!
        mo.md(
            '''
            # Hello, Markdown!
            Use marimo's "md" function to embed rich text into your marimo
            '''
        )
        """)`;
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(
        `# Hello, Markdown!\nmo.md(\n    '''\n    # Hello, Markdown!\n    Use marimo's "md" function to embed rich text into your marimo\n    '''\n)`,
      );
      expect(offset).toBe(9);
    });

    it("simple markdown", () => {
      const pythonCode = 'mo.md("# Title without proper delimiters")';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("# Title without proper delimiters");
      expect(offset).toBe(7);
    });

    it("should trim strings with leading and trailing whitespace", () => {
      const pythonCode = 'mo.md("""   \n# Title\nContent\n   """)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("# Title\nContent");
      expect(offset).toBe(9);
    });

    it("should handle space around the f-strings", () => {
      const pythonCode = 'mo.md(\n\t"""\n# Title\n{  Content  }\n"""\n)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("# Title\n{  Content  }");
      expect(offset).toBe(11);
    });

    it("should dedent indented strings", () => {
      const pythonCode =
        'mo.md(\n\t"""\n\t- item 1\n\t-item 2\n\t-item3\n\t"""\n)';
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("- item 1\n-item 2\n-item3");
      expect(offset).toBe(11);
    });

    it("should preserve escaped characters", () => {
      const pythonCode = `mo.md(r"$\\nu = \\mathllap{}\\cdot\\mathllap{\\alpha}$")`;
      const [innerCode, offset] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("$\\nu = \\mathllap{}\\cdot\\mathllap{\\alpha}$");
      expect(offset).toBe(8);
    });
  });

  describe("transformOut", () => {
    it("should wrap Markdown code with triple double-quoted string format", () => {
      const code = "# Markdown Title\n\nSome content here.";
      adapter.lastQuotePrefix = "";
      const [wrappedCode, offset] = adapter.transformOut(code);
      expect(wrappedCode).toMatchInlineSnapshot(`
        "mo.md(
            """
            # Markdown Title

            Some content here.
            """
        )"
      `);
      expect(offset).toBe(16);
    });

    it("should escape triple quotes in the Markdown code", () => {
      const code = 'Markdown with an escaped """quote"""!!';
      adapter.lastQuotePrefix = "";
      const [wrappedCode, offset] = adapter.transformOut(code);
      expect(wrappedCode).toBe(
        `mo.md("Markdown with an escaped \\"\\"\\"quote\\"\\"\\"!!")`,
      );
      expect(offset).toBe(7);
    });

    it.skip("should upgrade to an f-string if the code contains {}", () => {
      const code = "Markdown with an {foo} f-string";
      const [wrappedCode, offset] = adapter.transformOut(code);
      expect(wrappedCode).toBe(`mo.md(f"Markdown with an {foo} f-string")`);
      expect(offset).toBe(8);
    });

    it.skip("should upgrade to an f-string from r-string if the code contains {}", () => {
      const code = "Markdown with an {foo} f-string";
      adapter.lastQuotePrefix = "r";
      const [wrappedCode, offset] = adapter.transformOut(code);
      expect(wrappedCode).toBe(`mo.md(rf"Markdown with an {foo} f-string")`);
      expect(offset).toBe(9);
    });

    it("should not downgrade a f-string", () => {
      const code = "Normal markdown";
      adapter.lastQuotePrefix = "f";
      const [wrappedCode, offset] = adapter.transformOut(code);
      expect(wrappedCode).toBe('mo.md(f"Normal markdown")');
      expect(offset).toBe(8);
    });

    it("should not downgrade a rf-string", () => {
      const code = "Normal markdown";
      adapter.lastQuotePrefix = "rf";
      const [wrappedCode, offset] = adapter.transformOut(code);
      expect(wrappedCode).toBe('mo.md(rf"Normal markdown")');
      expect(offset).toBe(9);
    });

    it("should preserve r strings", () => {
      const code = "$\\nu = \\mathllap{}\\cdot\\mathllap{\\alpha}$";
      adapter.lastQuotePrefix = "r";
      const [wrappedCode, offset] = adapter.transformOut(code);
      const pythonCode = `mo.md(r"$\\nu = \\mathllap{}\\cdot\\mathllap{\\alpha}$")`;
      expect(wrappedCode).toBe(pythonCode);
      expect(offset).toBe(8);
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

    it("should return false sequences that look like markdown but are not", () => {
      const once = 'mo.md("""# Markdown Title\n\nSome content here""")';
      const pythonCode = [once, once].join("\n");
      expect(adapter.isSupported(pythonCode)).toBe(false);
    });
  });
});
