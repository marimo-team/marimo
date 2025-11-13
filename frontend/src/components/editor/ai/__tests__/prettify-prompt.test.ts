/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { prettifyPromptToMarkdown } from "../add-cell-with-ai";

describe("prettifyPromptToMarkdown", () => {
  it("wraps prompt text in a markdown cell", () => {
    const prompt = "generate an altair chart with @data://pokemon";
    const result = prettifyPromptToMarkdown(prompt);

    expect(result).toMatchInlineSnapshot(`"mo.md(f"""
\`\`\`md
generate an altair chart with @data://pokemon
\`\`\`
<p align="center"><i>Generating with AI...</i></p>
""")"`);
  });

  it("escapes consecutive double quotes inside the prompt", () => {
    const prompt = 'say ""hello""';
    const result = prettifyPromptToMarkdown(prompt);

    expect(result).toMatchInlineSnapshot(`"mo.md(f"""
\`\`\`md
say "\\"hello"\\"
\`\`\`
<p align="center"><i>Generating with AI...</i></p>
""")"`);
  });
});
