/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { createLspMarkdownRenderer } from "../markdown-renderer";

describe("createLspMarkdownRenderer", () => {
  it("syntax-highlights python code blocks with tok-* span classes", () => {
    const render = createLspMarkdownRenderer();
    const result = render("```python\ndef foo():\n    pass\n```");
    expect(result).toContain('class="language-python"');
    expect(result).toContain("tok-keyword");
    expect(result).toContain("<pre><code");
  });

  it("does not highlight non-python code blocks", () => {
    const render = createLspMarkdownRenderer();
    const result = render("```bash\necho hello\n```");
    expect(result).not.toContain("tok-keyword");
    expect(result).toContain("<code");
  });

  it("renders empty python code blocks as empty string", () => {
    const render = createLspMarkdownRenderer();
    const result = render("```python\n   \n```");
    expect(result).toBe("");
  });

  it("renders markdown prose unchanged", () => {
    const render = createLspMarkdownRenderer();
    const result = render("## Examples\n\nSome text.");
    expect(result).toContain("<h2");
    expect(result).toContain("Examples");
    expect(result).toContain("Some text.");
  });

  it("escapes HTML in highlighted code", () => {
    const render = createLspMarkdownRenderer();
    const result = render('```python\nx = "<div>"\n```');
    expect(result).not.toContain("<div>");
    expect(result).toContain("&lt;div&gt;");
  });
});
