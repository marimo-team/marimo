/* Copyright 2026 Marimo. All rights reserved. */
import { classHighlighter, highlightCode } from "@lezer/highlight";
import { parser as pythonParser } from "@lezer/python";
import { marked } from "marked";

/**
 * Syntax-highlight a Python code string using the lezer Python parser.
 * Returns an HTML string with tok-* span classes for styling.
 */
function highlightPython(code: string): string {
  const tree = pythonParser.parse(code);
  let html = "";
  highlightCode(
    code,
    tree,
    classHighlighter,
    (text, classes) => {
      const escaped = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
      html += classes ? `<span class="${classes}">${escaped}</span>` : escaped;
    },
    () => {
      html += "\n";
    },
  );
  return html;
}

/**
 * A markdown renderer for LSP hover tooltips that adds syntax highlighting
 * to Python code blocks using the lezer Python parser and classHighlighter.
 * The tok-* CSS classes are defined in documentation.css.
 */
export function createLspMarkdownRenderer(): (markdown: string) => string {
  const renderer = new marked.Renderer();
  const prevCode = renderer.code.bind(renderer);

  renderer.code = (token) => {
    const { text, lang } = token;
    if (!text.trim()) {
      return "";
    }
    if (lang === "python" || lang === "py") {
      const highlighted = highlightPython(text);
      return `<pre><code class="language-python">${highlighted}</code></pre>\n`;
    }
    return prevCode(token);
  };

  return (markdown: string): string =>
    marked(markdown, {
      async: false,
      gfm: true,
      breaks: true,
      renderer,
    }) as string;
}
