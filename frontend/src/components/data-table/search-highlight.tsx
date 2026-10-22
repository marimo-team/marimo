/* Copyright 2026 Marimo. All rights reserved. */

import type { ReactNode } from "react";

/**
 * Build the pattern that `highlightMatches` uses to find `query` in a
 * display string. Returns `undefined` for an empty query. The query is
 * matched as a literal, case-insensitive substring, which mirrors how the
 * backend selects rows.
 */
export function buildHighlightPattern(query?: string): RegExp | undefined {
  if (!query) {
    return undefined;
  }
  const escaped = query.replace(/[$()*+.?[\\\]^{|}]/g, "\\$&");
  return new RegExp(`(${escaped})`, "gi");
}

/**
 * Split `text` into plain segments and `<mark>` segments for every match of
 * `pattern`. Returns `text` unchanged when `pattern` is absent or does not
 * match. `pattern` must wrap its whole body in one capture group so that
 * matches land on the odd indexes of `String.prototype.split`.
 */
export function highlightMatches(text: string, pattern?: RegExp): ReactNode {
  if (!pattern) {
    return text;
  }
  const parts = text.split(pattern);
  if (parts.length === 1) {
    return text;
  }
  return parts
    .map((part, idx) =>
      idx % 2 === 1 ? (
        <mark key={idx} className="bg-search-highlight text-inherit">
          {part}
        </mark>
      ) : (
        part
      ),
    )
    .filter((part) => part !== "");
}
