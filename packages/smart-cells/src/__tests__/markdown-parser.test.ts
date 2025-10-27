/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { MarkdownParser } from "../parsers/markdown-parser.js";

const parser = new MarkdownParser();

describe("MarkdownParser", () => {
  describe("transformIn", () => {
    it("should extract markdown from triple double-quoted strings", () => {
      const pythonCode = 'mo.md("""# Markdown Title\n\nSome content here.""")';
      const { code, offset, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe("# Markdown Title\n\nSome content here.");
      expect(offset).toBe(9);
      expect(metadata.quotePrefix).toBe("");
    });

    it("should handle single double-quoted strings", () => {
      const pythonCode = 'mo.md("Some *markdown* content")';
      const { code, offset, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe("Some *markdown* content");
      expect(offset).toBe(7);
      expect(metadata.quotePrefix).toBe("");
    });

    it("should handle f-strings", () => {
      const pythonCode = 'mo.md(f"""# Title\n{some_variable}""")';
      const { code, offset, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe("# Title\n{some_variable}");
      expect(offset).toBe(10);
      expect(metadata.quotePrefix).toBe("f");
    });

    it("should handle f-strings with method calls containing strings", () => {
      const pythonCode = `mo.md(f"""# User: {get_user("john")}""")`;
      const { code, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe(`# User: {get_user("john")}`);
      expect(metadata.quotePrefix).toBe("f");
    });

    it("should handle f-strings with complex expressions containing quotes", () => {
      const pythonCode = `mo.md(f"""# Count: {",".join(data["items"])}""")`;
      const { code, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe(`# Count: {",".join(data["items"])}`);
      expect(metadata.quotePrefix).toBe("f");
    });

    it("should handle f-strings with nested brackets and quotes", () => {
      const pythonCode = `mo.md(f"""
# Report
User: {users["name"][0]}
Count: {str(data["items"][0]["count"])}
""")`;
      const { code, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe(
        `# Report
User: {users["name"][0]}
Count: {str(data["items"][0]["count"])}`.trim(),
      );
      expect(metadata.quotePrefix).toBe("f");
    });

    it("should handle r-strings", () => {
      const pythonCode = `mo.md(r"$\\nu = \\mathllap{}\\cdot\\mathllap{\\alpha}$")`;
      const { code, offset, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe(String.raw`$\nu = \mathllap{}\cdot\mathllap{\alpha}$`);
      expect(offset).toBe(8);
      expect(metadata.quotePrefix).toBe("r");
    });

    it("should handle rf-strings", () => {
      const pythonCode = 'mo.md(rf"""# Title\n{some_variable}""")';
      const { code, offset, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe("# Title\n{some_variable}");
      expect(offset).toBe(11);
      expect(metadata.quotePrefix).toBe("rf");
    });

    it("should unescape quotes", () => {
      const pythonCode = String.raw`mo.md("""This is some \"""content\"""!""")`;
      const { code } = parser.transformIn(pythonCode);
      expect(code).toBe(`This is some """content"""!`);
    });

    it("should dedent indented strings", () => {
      const pythonCode =
        'mo.md(\n\t"""\n\t- item 1\n\t-item 2\n\t-item3\n\t"""\n)';
      const { code } = parser.transformIn(pythonCode);
      expect(code).toBe("- item 1\n-item 2\n-item3");
    });

    it("should handle empty strings", () => {
      const { code, offset } = parser.transformIn('mo.md("")');
      expect(code).toBe("");
      expect(offset).toBe(0);
    });

    it("should return original code for unsupported format", () => {
      const pythonCode = 'print("Hello, World!")';
      const { code, offset } = parser.transformIn(pythonCode);
      expect(code).toBe('print("Hello, World!")');
      expect(offset).toBe(0);
    });
  });

  describe("transformOut", () => {
    it("should wrap single line markdown", () => {
      const code = "Hello world";
      const { code: pythonCode, offset } = parser.transformOut(code, {
        quotePrefix: "",
      });
      expect(pythonCode).toBe(`mo.md("""Hello world""")`);
      expect(offset).toBe(9);
    });

    it("should wrap multiline markdown", () => {
      const code = "# Markdown Title\n\nSome content here.";
      const { code: pythonCode, offset } = parser.transformOut(code, {
        quotePrefix: "",
      });
      expect(pythonCode).toMatchInlineSnapshot(`
        "mo.md(
            """
        # Markdown Title

        Some content here.
        """
        )"
      `);
      expect(offset).toBe(16);
    });

    it("should preserve r-string prefix", () => {
      const code = String.raw`$\nu = \mathllap{}\cdot\mathllap{\alpha}$`;
      const { code: pythonCode } = parser.transformOut(code, {
        quotePrefix: "r",
      });
      expect(pythonCode).toBe(
        `mo.md(r"""$\\nu = \\mathllap{}\\cdot\\mathllap{\\alpha}$""")`,
      );
    });

    it("should preserve f-string prefix", () => {
      const code = "# Title\n{some_variable}";
      const { code: pythonCode } = parser.transformOut(code, {
        quotePrefix: "f",
      });
      expect(pythonCode).toMatchInlineSnapshot(`
        "mo.md(
            f"""
        # Title
        {some_variable}
        """
        )"
      `);
    });

    it("should escape triple quotes", () => {
      const code = 'Markdown with an escaped """quote"""!!';
      const { code: pythonCode } = parser.transformOut(code, {
        quotePrefix: "",
      });
      expect(pythonCode).toBe(
        `mo.md("""Markdown with an escaped \\"""quote\\"""!!""")`,
      );
    });

    it("should handle empty string", () => {
      const { code: pythonCode } = parser.transformOut("", {
        quotePrefix: "r",
      });
      expect(pythonCode).toBe(`mo.md(r""" """)`);
    });
  });

  describe("isSupported", () => {
    it("should return true for valid formats", () => {
      const validCases = [
        'mo.md("""# Markdown""")',
        "mo.md()",
        'mo.md("")',
        "mo.md(f'hello world')",
        'mo.md(r"hello world")',
        "mo.md(rf'hello world')",
        'mo.md(fr"hello world")',
        // Complex f-strings with embedded expressions
        `mo.md(f"""# User: {get_user("john")}""")`,
        `mo.md(f"""# Count: {",".join(data["items"])}""")`,
        `mo.md(f"""# Report: {str(data["items"][0]["count"])}""")`,
      ];

      for (const pythonCode of validCases) {
        expect(parser.isSupported(pythonCode)).toBe(true);
      }
    });

    it("should return false for invalid formats", () => {
      const invalidCases = [
        'print("Hello, World!")',
        'mo.md("test"), mo.md("test2")', // Multiple calls
        'mo.md("test"); print("hi")', // Additional statements
      ];

      for (const pythonCode of invalidCases) {
        expect(parser.isSupported(pythonCode)).toBe(false);
      }
    });

    it("should return true for empty string", () => {
      expect(parser.isSupported("")).toBe(true);
    });
  });

  describe("roundtrip", () => {
    it("should roundtrip markdown correctly", () => {
      const originalMarkdown = "# Hello\n\nThis is **bold** text.";
      const pythonCode = MarkdownParser.fromMarkdown(originalMarkdown);
      const { code, metadata } = parser.transformIn(pythonCode);
      expect(code).toBe(originalMarkdown);

      const { code: backToPython } = parser.transformOut(code, metadata);
      const { code: roundtripped } = parser.transformIn(backToPython);
      expect(roundtripped).toBe(originalMarkdown);
    });
  });
});
