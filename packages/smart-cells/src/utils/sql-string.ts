/* Copyright 2026 Marimo. All rights reserved. */

import { parsePythonAST } from "./python-ast.js";

/** Encode literal SQL text at the Python string boundary. */
export function escapeSQLString(text: string, fString = true): string {
  const escaped = text
    .replaceAll("\\", "\\\\")
    .replaceAll(/"{3,}/g, (quotes) => quotes.replaceAll('"', '\\"'))
    .replaceAll("\r", "\\r")
    .replaceAll("\n", "\\n");
  return fString
    ? escaped.replaceAll("{", "{{").replaceAll("}", "}}")
    : escaped;
}

/** The SQL editor contains Python string source, including intentional fields. */
export function escapeSQLQuoteRuns(source: string, fString = true): string {
  if (!source.includes('"""')) {
    return source;
  }
  if (fString) {
    const fields = getSQLInterpolationRanges(source);
    if (fields.length > 0) {
      let end = 0;
      const parts: string[] = [];
      for (const { from, to } of fields) {
        parts.push(
          escapeSQLQuoteRuns(source.slice(end, from), false),
          source.slice(from, to),
        );
        end = to;
      }
      parts.push(escapeSQLQuoteRuns(source.slice(end), false));
      return parts.join("");
    }
  }
  return source.replaceAll(
    /(\\*)("{3,})/g,
    (_, slashes: string, quotes: string) => {
      const firstQuote = slashes.length % 2 === 0 ? '\\"' : '"';
      return slashes + firstQuote + '\\"'.repeat(quotes.length - 1);
    },
  );
}

/** Positions of intentional Python fields, excluding doubled literal braces. */
export function getSQLInterpolationRanges(
  source: string,
): Array<{ from: number; to: number }> {
  if (
    ![...source.matchAll(/\{+/g)].some((match) => match[0].length % 2 === 1)
  ) {
    return [];
  }
  for (const quote of ['"""', "'''"]) {
    const wrapped = `f${quote}${source}${quote}`;
    const node = parsePythonAST(wrapped).topNode.firstChild?.firstChild;
    if (node?.name === "FormatString" && node.to === wrapped.length) {
      return node
        .getChildren("FormatReplacement")
        .map((child) => ({ from: child.from - 4, to: child.to - 4 }))
        .filter(({ to }) => source[to - 1] === "}");
    }
  }
  return [];
}
