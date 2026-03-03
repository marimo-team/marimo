/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import {
  normalizeLspDocumentation,
  normalizeMarkdownMath,
} from "../normalize-markdown-math";

describe("normalizeMarkdownMath", () => {
  it("converts rst math directives to marimo-tex display math", () => {
    const markdown = `
For t > 0:

.. math::

    m_t = \\beta_1 \\cdot m_{t-1}
`.trim();

    const normalized = normalizeMarkdownMath(markdown);
    expect(normalized).not.toContain(".. math::");
    expect(normalized).toContain("<marimo-tex");
    expect(normalized).toContain("||[m_t = \\beta_1 \\cdot m_{t-1}||]");
  });

  it("converts :math: roles and latex delimiters", () => {
    const markdown =
      "Inline :math:`x^2`, \\(y^2\\), \\[z^2\\], $a^2$, and $$b^2$$.";

    const normalized = normalizeMarkdownMath(markdown);
    expect(normalized).not.toContain(":math:`");
    expect(normalized).not.toContain("\\(");
    expect(normalized).not.toContain("\\[");
    expect(normalized).toContain("<marimo-tex");
    expect(normalized).toContain("||(x^2||)");
    expect(normalized).toContain("||(y^2||)");
    expect(normalized).toContain("||[z^2||]");
    expect(normalized).toContain("||(a^2||)");
    expect(normalized).toContain("||[b^2||]");
  });

  it("converts rst math directives with same-line latex", () => {
    const markdown =
      ".. math::\\begin{align*} m_t &= \\beta_1 g_t \\\\ v_t &= \\beta_2 g_t^2 \\end{align*}";

    const normalized = normalizeMarkdownMath(markdown);
    expect(normalized).not.toContain(".. math::");
    expect(normalized).toContain("<marimo-tex");
    expect(normalized).toContain(
      "||[\\begin{align*} m_t &= \\beta_1 g_t \\\\ v_t &= \\beta_2 g_t^2 \\end{align*}||]",
    );
  });

  it("converts rst math directives followed by unindented latex blocks", () => {
    const markdown = `
.. math::

\\begin{align*}
m_t &= \\beta_1 g_t \\\\
v_t &= \\beta_2 g_t^2
\\end{align*}
`.trim();

    const normalized = normalizeMarkdownMath(markdown);
    expect(normalized).not.toContain(".. math::");
    expect(normalized).toContain("<marimo-tex");
    expect(normalized).toContain(
      "||[\\begin{align*}\nm_t &= \\beta_1 g_t \\\\\nv_t &= \\beta_2 g_t^2\n\\end{align*}||]",
    );
  });

  it("does not transform fenced code blocks or inline code spans", () => {
    const markdown = `
\`\`\`python
formula = ":math:\`x\`"
directive = """
.. math::

    x^2
"""
\`\`\`

Use \`:math:\` as text and :math:\`z\` as math.
`.trim();

    const normalized = normalizeMarkdownMath(markdown);

    expect(normalized).toContain('formula = ":math:`x`"');
    expect(normalized).toContain(".. math::");
    expect(normalized).toContain("`:math:` as text");
    expect(normalized).not.toContain(":math:`z`");
    expect(normalized).toContain("||(z||)");
  });
});

describe("normalizeLspDocumentation", () => {
  it("normalizes markdown and plaintext math markup content", () => {
    const markdownDoc = normalizeLspDocumentation({
      kind: "markdown",
      value: "Compute :math:`x^2`",
    });
    const plaintextMathDoc = normalizeLspDocumentation({
      kind: "plaintext",
      value: "Compute :math:`x^2`",
    });
    const plaintextDoc = normalizeLspDocumentation({
      kind: "plaintext",
      value: "Price is $5 today",
    });

    expect(markdownDoc).toEqual({
      kind: "markdown",
      value: 'Compute <marimo-tex class="arithmatex">||(x^2||)</marimo-tex>',
    });
    expect(plaintextMathDoc).toEqual({
      kind: "markdown",
      value: 'Compute <marimo-tex class="arithmatex">||(x^2||)</marimo-tex>',
    });
    expect(plaintextDoc).toEqual({
      kind: "plaintext",
      value: "Price is $5 today",
    });
  });
});
