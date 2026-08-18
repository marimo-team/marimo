/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { jsonToMarkdown } from "../json-parser";

describe("jsonToMarkdown URL linkification", () => {
  it("links a plain URL", () => {
    const md = jsonToMarkdown([{ link: "https://marimo.io/path" }]);
    expect(md).toContain(
      "[https://marimo.io/path](https://marimo.io/path)",
    );
  });

  it("stops the link at the JSON delimiter, not the trailing quote (#10567)", () => {
    const md = jsonToMarkdown([
      { attachments: '[{"url":"https://example.com/p/AAA"}]' },
    ]);
    // The link target ends exactly at the URL; the closing `"}]` is left as
    // text rather than pulled into the href.
    expect(md).toContain("(https://example.com/p/AAA)");
    expect(md).not.toContain('https://example.com/p/AAA"');
  });

  it("does not swallow a trailing double-quote into the link", () => {
    const md = jsonToMarkdown([{ v: '"https://example.com/x"' }]);
    expect(md).toContain("(https://example.com/x)");
    expect(md).not.toContain('https://example.com/x"');
  });

  it("leaves existing markdown links untouched", () => {
    const md = jsonToMarkdown([
      { v: "[docs](https://marimo.io/docs)" },
    ]);
    expect(md).toContain("[docs](https://marimo.io/docs)");
    // Must not double-wrap into [[docs](url)](url).
    expect(md).not.toContain("[[docs]");
  });
});
