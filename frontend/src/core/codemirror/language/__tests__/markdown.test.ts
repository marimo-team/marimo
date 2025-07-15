/* Copyright 2024 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it } from "vitest";
import {
  MarkdownLanguageAdapter,
  type MarkdownLanguageAdapterMetadata,
} from "../languages/markdown";
import { getQuotePrefix } from "../panel/markdown";

const adapter = new MarkdownLanguageAdapter();

describe("MarkdownLanguageAdapter", () => {
  describe("defaultMetadata", () => {
    it("should be set", () => {
      expect(adapter.defaultMetadata).toMatchInlineSnapshot(`
        {
          "quotePrefix": "r",
        }
      `);
    });
  });

  describe("transformIn", () => {
    it("empty", () => {
      const [innerCode, offset, metadata] = adapter.transformIn("");
      expect(innerCode).toBe("");
      expect(offset).toBe(0);
      const out = adapter.transformOut(innerCode, metadata);
      expect(out).toMatchInlineSnapshot(`
        [
          "mo.md(r""" """)",
          10,
        ]
      `);
    });

    it("should extract inner Markdown from triple double-quoted strings", () => {
      const pythonCode = 'mo.md("""# Markdown Title\n\nSome content here.""")';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("# Markdown Title\n\nSome content here.");
      expect(offset).toBe(9);
      expect(metadata.quotePrefix).toBe("");
    });

    it("should handle single double-quoted strings", () => {
      const pythonCode = 'mo.md("Some *markdown* content")';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("Some *markdown* content");
      expect(offset).toBe(7);
      expect(metadata.quotePrefix).toBe("");
    });

    it("should handle triple single-quoted strings", () => {
      const pythonCode = "mo.md('''# Another Title\nContent''')";
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("# Another Title\nContent");
      expect(offset).toBe(9);
      expect(metadata.quotePrefix).toBe("");
    });

    it("should still transform if no markdown is detected", () => {
      const pythonCode = 'print("Hello, World!")';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe('print("Hello, World!")');
      expect(offset).toBe(0);
      expect(metadata.quotePrefix).toBe("r");
    });

    it("should handle an empty string", () => {
      const pythonCode = 'mo.md("")';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("");
      expect(offset).toBe(0);
      expect(metadata.quotePrefix).toBe("");
    });

    it("should unescape code blocks", () => {
      // """
      const pythonCode2 = String.raw`mo.md("""This is some \"""content\"""!""")`;
      const [innerCode2, offset2, metadata2] = adapter.transformIn(pythonCode2);
      expect(innerCode2).toBe(`This is some """content"""!`);
      expect(offset2).toBe(9);
      expect(metadata2.quotePrefix).toBe("");

      // "
      const pythonCode3 = String.raw`mo.md("This is some \"content\"!")`;
      const [innerCode3, offset3, metadata3] = adapter.transformIn(pythonCode3);
      expect(innerCode3).toBe(`This is some "content"!`);
      expect(offset3).toBe(7);
      expect(metadata3.quotePrefix).toBe("");

      // '
      const pythonCode4 = String.raw`mo.md('This is some \'content\'!')`;
      const [innerCode4, offset4, metadata4] = adapter.transformIn(pythonCode4);
      expect(innerCode4).toBe(`This is some 'content'!`);
      expect(offset4).toBe(7);
      expect(metadata4.quotePrefix).toBe("");
    });

    it("should handle strings with escaped quotes", () => {
      const pythonCode = String.raw`mo.md("""Markdown with an escaped \"quote\"""")`;
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(String.raw`Markdown with an escaped \"quote\"`);
      expect(offset).toBe('mo.md("""'.length);
      expect(metadata.quotePrefix).toBe("");
    });

    it("should handle strings with nested markdown", () => {
      const pythonCode =
        'mo.md("""# Title\n\n```python\nprint("Hello, Markdown!")\n```""")';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(
        '# Title\n\n```python\nprint("Hello, Markdown!")\n```',
      );
      expect(offset).toBe('mo.md("""'.length);
      expect(metadata.quotePrefix).toBe("");
    });

    it("should convert to markdown anyways", () => {
      const pythonCode = 'print("No markdown here")';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(`print("No markdown here")`);
      expect(offset).toBe(0);
      expect(metadata.quotePrefix).toBe("r");
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
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(
        `# Hello, Markdown!\nmo.md(\n    '''\n    # Hello, Markdown!\n    Use marimo's "md" function to embed rich text into your marimo\n    '''\n)`,
      );
      expect(offset).toBe(9);
      expect(metadata.quotePrefix).toBe("");
    });

    it("simple markdown", () => {
      const pythonCode = 'mo.md("# Title without proper delimiters")';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("# Title without proper delimiters");
      expect(offset).toBe(7);
      expect(metadata.quotePrefix).toBe("");
    });

    it("should trim strings with leading and trailing whitespace", () => {
      const pythonCode = 'mo.md("""   \n# Title\nContent\n   """)';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("# Title\nContent");
      expect(offset).toBe(9);
      expect(metadata.quotePrefix).toBe("");
    });

    it("should handle space around the f-strings", () => {
      const pythonCode = 'mo.md(\n\t"""\n# Title\n{  Content  }\n"""\n)';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("# Title\n{  Content  }");
      expect(offset).toBe(11);
      expect(metadata.quotePrefix).toBe("");
    });

    it("should dedent indented strings", () => {
      const pythonCode =
        'mo.md(\n\t"""\n\t- item 1\n\t-item 2\n\t-item3\n\t"""\n)';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("- item 1\n-item 2\n-item3");
      expect(offset).toBe(11);
      expect(metadata.quotePrefix).toBe("");
    });

    it("should preserve escaped characters", () => {
      const pythonCode = `mo.md(r"$\\nu = \\mathllap{}\\cdot\\mathllap{\\alpha}$")`;
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe(
        String.raw`$\nu = \mathllap{}\cdot\mathllap{\alpha}$`,
      );
      expect(offset).toBe(8);
      expect(metadata.quotePrefix).toBe("r");
    });

    it("should preserve indentation in f-strings", () => {
      const pythonCode =
        'mo.md(\n    f"""\n```python\n{some_variable}\n```\n"""\n)';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("```python\n{some_variable}\n```");
      expect(offset).toBe(15);
      expect(metadata.quotePrefix).toBe("f");

      // Transform out
      const [outerCode, outerOffset] = adapter.transformOut(
        innerCode,
        metadata,
      );
      expect(outerCode).toMatch(pythonCode);
      expect(outerOffset).toBe(17);
    });

    it("should handle f-strings", () => {
      const pythonCode = 'mo.md(f"""# Title\n{some_variable}""")';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("# Title\n{some_variable}");
      expect(offset).toBe(10);
      expect(metadata.quotePrefix).toBe("f");
    });

    it("should handle rf-strings", () => {
      const pythonCode = 'mo.md(rf"""# Title\n{some_variable}""")';
      const [innerCode, offset, metadata] = adapter.transformIn(pythonCode);
      expect(innerCode).toBe("# Title\n{some_variable}");
      expect(offset).toBe(11);
      expect(metadata.quotePrefix).toBe("rf");
    });
  });

  describe("transformOut", () => {
    const metadata: MarkdownLanguageAdapterMetadata = { quotePrefix: "" };

    beforeEach(() => {
      metadata.quotePrefix = "";
    });

    it("empty string", () => {
      const code = "";
      const [wrappedCode, offset] = adapter.transformOut(code, metadata);
      expect(wrappedCode).toBe(`mo.md(""" """)`);
      expect(offset).toBe(9);
    });

    it("defaults to r-string when there is no last quote prefix", () => {
      const adapter = new MarkdownLanguageAdapter();
      const code = "Hello world";
      metadata.quotePrefix = "r";
      const [wrappedCode, offset] = adapter.transformOut(code, metadata);
      expect(wrappedCode).toBe(`mo.md(r"""Hello world""")`);
      expect(offset).toBe(10);
    });

    it("single line", () => {
      const code = "Hello world";
      const [wrappedCode, offset] = adapter.transformOut(code, metadata);
      expect(wrappedCode).toBe(`mo.md("""Hello world""")`);
      expect(offset).toBe(9);
    });

    it("starts with quote", () => {
      const code = '"Hello" world';
      const [wrappedCode, offset] = adapter.transformOut(code, metadata);
      expect(wrappedCode).toMatchInlineSnapshot(`
        "mo.md(
            """
        "Hello" world
        """
        )"
      `);
      expect(offset).toBe(16);
    });

    it("ends with quote", () => {
      const code = 'Hello "world"';
      const [wrappedCode, offset] = adapter.transformOut(code, metadata);
      expect(wrappedCode).toMatchInlineSnapshot(`
        "mo.md(
            """
        Hello "world"
        """
        )"
      `);
      expect(offset).toBe(16);
    });

    it("should wrap Markdown code with triple double-quoted string format", () => {
      const code = "# Markdown Title\n\nSome content here.";
      const [wrappedCode, offset] = adapter.transformOut(code, metadata);
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
      const [wrappedCode, offset] = adapter.transformOut(code, metadata);
      expect(wrappedCode).toBe(
        `mo.md("""Markdown with an escaped \\"""quote\\"""!!""")`,
      );
      expect(offset).toBe(9);
    });

    it("should preserve r strings", () => {
      const code = String.raw`$\nu = \mathllap{}\cdot\mathllap{\alpha}$`;
      metadata.quotePrefix = "r";
      const [wrappedCode, offset] = adapter.transformOut(code, metadata);
      const pythonCode = `mo.md(r"""$\\nu = \\mathllap{}\\cdot\\mathllap{\\alpha}$""")`;
      expect(wrappedCode).toBe(pythonCode);
      expect(offset).toBe(10);
    });

    it("should handle f-strings in transformOut", () => {
      const code = "# Title\n{some_variable}";
      metadata.quotePrefix = "f";
      const [wrappedCode, offset] = adapter.transformOut(code, metadata);
      expect(wrappedCode).toMatchInlineSnapshot(`
        "mo.md(
            f"""
        # Title
        {some_variable}
        """
        )"
      `);
      expect(offset).toBe(17);
    });

    it("should handle rf-strings in transformOut", () => {
      const code = "# Title\n{some_variable}";
      metadata.quotePrefix = "rf";
      const [wrappedCode, offset] = adapter.transformOut(code, metadata);
      expect(wrappedCode).toMatchInlineSnapshot(`
        "mo.md(
            rf"""
        # Title
        {some_variable}
        """
        )"
      `);
      expect(offset).toBe(18);
    });
  });

  describe("isSupported", () => {
    it("should return true for supported markdown string formats", () => {
      const pythonCode = 'mo.md("""# Markdown Title\n\nSome content here.""")';
      const VALID_FORMATS = [
        pythonCode,
        "mo.md()",
        "mo.md('')",
        'mo.md("")',
        'mo.md(""" hi """)',
        "mo.md(''' hi ''')",
        "mo.md(f'hello world')",
        'mo.md(f"hello world")',
        "mo.md(r'hello world')",
        'mo.md(r"hello world")',
        "mo.md(rf'hello world')",
        'mo.md(rf"hello world")',
        "mo.md(fr'hello world')",
        'mo.md(fr"hello world")',
        'mo.md(f"""\n```python\n{some_variable}\n```\n""")',
        "mo.md(f'''\n```python\n{some_variable}\n```\n''')",
        'mo.md(rf"""\n```python\n{some_variable}\n```\n""")',
        "mo.md(rf'''\n```python\n{some_variable}\n```\n''')",
        'mo.md(f"""{np.random.randint(0, 10)}""")',
      ];
      for (const format of VALID_FORMATS) {
        expect(adapter.isSupported(format)).toBe(true);
      }
    });

    it("should return true for complex nested markdown", () => {
      const pythonCode = String.raw`
      mo.md(
        rf"""
        \`\`\`python
        {pathlib.Path(__file__).read_text(encoding="utf-8")}
        \`\`\`
        """
      )
      `;
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

    it("should return false for multiple markdown blocks in a single string", () => {
      const pythonCode = `mo.md("this is markdown"), mo.md("this is not markdown")`;
      expect(adapter.isSupported(pythonCode)).toBe(false);
    });

    it("should return false for multiple mo statements blocks in a single string", () => {
      const CASES = [
        `mo.md("this is markdown"), mo.plain_text("this is not markdown")`,
        `mo.plain_text("this is not markdown"), mo.md("this is markdown")`,
        `mo.md("this is markdown"), mo.md("this is markdown")`,
        `mo.plain_text("this is not markdown"), mo.plain_text("this is not markdown")`,
      ];
      for (const pythonCode of CASES) {
        expect(adapter.isSupported(pythonCode)).toBe(false);
      }
    });

    it("should return true when the mo calls are just strings inside the markdown", () => {
      const CASES = [
        `mo.md("this is markdown, mo.plain_text('this is not markdown')")`,
        `mo.md("this is markdown, mo.md('this is markdown')")`,
        `mo.md("this is markdown, mo.md('this is markdown'), mo.plain_text('this is not markdown')")`,
        `mo.md("""this is markdown, mo.plain_text('this is not markdown')""")`,
        `mo.md("""this is markdown, mo.md('this is markdown')""")`,
        `mo.md("""this is markdown, mo.md('this is markdown'), mo.plain_text('this is not markdown')""")`,
        `mo.md(r"""this is markdown, mo.plain_text('this is not markdown')""")`,
        `mo.md(r"""this is markdown, mo.md('this is markdown')""")`,
        `mo.md(r"""this is markdown, mo.md('this is markdown'), mo.plain_text('this is not markdown')""")`,
      ];
      for (const pythonCode of CASES) {
        expect(adapter.isSupported(pythonCode)).toBe(true);
      }
    });
  });
});

describe("getQuotePrefix", () => {
  it("should return the correct quote prefix when checked", () => {
    expect(
      getQuotePrefix({ currentQuotePrefix: "", checked: true, prefix: "r" }),
    ).toBe("r");
    expect(
      getQuotePrefix({ currentQuotePrefix: "", checked: true, prefix: "f" }),
    ).toBe("f");
    expect(
      getQuotePrefix({ currentQuotePrefix: "r", checked: true, prefix: "f" }),
    ).toBe("rf");
    expect(
      getQuotePrefix({ currentQuotePrefix: "f", checked: true, prefix: "r" }),
    ).toBe("rf");
  });

  it("should return the correct quote prefix when unchecked", () => {
    expect(
      getQuotePrefix({ currentQuotePrefix: "r", checked: false, prefix: "r" }),
    ).toBe("");
    expect(
      getQuotePrefix({ currentQuotePrefix: "f", checked: false, prefix: "f" }),
    ).toBe("");
    expect(
      getQuotePrefix({ currentQuotePrefix: "rf", checked: false, prefix: "r" }),
    ).toBe("f");
    expect(
      getQuotePrefix({ currentQuotePrefix: "rf", checked: false, prefix: "f" }),
    ).toBe("r");
  });

  it("should return the correct quote prefix even when not possible to toggle", () => {
    expect(
      getQuotePrefix({ currentQuotePrefix: "", checked: false, prefix: "r" }),
    ).toBe("");
    expect(
      getQuotePrefix({ currentQuotePrefix: "", checked: false, prefix: "f" }),
    ).toBe("");
    expect(
      getQuotePrefix({ currentQuotePrefix: "r", checked: false, prefix: "f" }),
    ).toBe("r");
    expect(
      getQuotePrefix({ currentQuotePrefix: "f", checked: false, prefix: "r" }),
    ).toBe("f");

    expect(
      getQuotePrefix({ currentQuotePrefix: "rf", checked: true, prefix: "r" }),
    ).toBe("rf");
    expect(
      getQuotePrefix({ currentQuotePrefix: "rf", checked: true, prefix: "f" }),
    ).toBe("rf");
    expect(
      getQuotePrefix({ currentQuotePrefix: "f", checked: true, prefix: "f" }),
    ).toBe("f");
    expect(
      getQuotePrefix({ currentQuotePrefix: "r", checked: true, prefix: "r" }),
    ).toBe("r");

    expect(
      getQuotePrefix({ currentQuotePrefix: "", checked: false, prefix: "" }),
    ).toBe("");
    expect(
      getQuotePrefix({ currentQuotePrefix: "", checked: true, prefix: "" }),
    ).toBe("");
  });
});
