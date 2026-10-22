/* Copyright 2026 Marimo. All rights reserved. */

import type { ReactNode } from "react";

/** Half-open `[start, end)` offsets into a string. */
export type MatchRange = readonly [start: number, end: number];

/**
 * Build the pattern that finds `query` in a display string. Returns
 * `undefined` for an empty query. The query is matched as a literal,
 * case-insensitive substring, which mirrors how the backend selects rows.
 * The `u` flag selects Unicode simple case folding, the same folding the
 * backend regex engines use.
 */
export function buildHighlightPattern(query?: string): RegExp | undefined {
  if (!query) {
    return undefined;
  }
  const escaped = query.replace(/[$()*+.?[\\\]^{|}]/g, "\\$&");
  return new RegExp(escaped, "giu");
}

/** Offsets of every match of `pattern` in `text`. */
export function findMatchRanges(text: string, pattern?: RegExp): MatchRange[] {
  if (!pattern) {
    return [];
  }
  const ranges: MatchRange[] = [];
  for (const match of text.matchAll(pattern)) {
    ranges.push([match.index, match.index + match[0].length]);
  }
  return ranges;
}

/**
 * Wrap the parts of `text` covered by `ranges` in `<mark>` elements.
 * `ranges` are offsets into a larger string in which `text` starts at
 * `offset`, so one set of ranges can be shared across adjacent segments.
 * Returns `text` unchanged when no range overlaps it.
 */
export function highlightRanges(
  text: string,
  ranges: readonly MatchRange[],
  offset = 0,
): ReactNode {
  const segments: ReactNode[] = [];
  let cursor = 0;
  for (const [rangeStart, rangeEnd] of ranges) {
    const start = Math.max(rangeStart - offset, cursor);
    const end = Math.min(rangeEnd - offset, text.length);
    if (end <= start) {
      continue;
    }
    if (start > cursor) {
      segments.push(text.slice(cursor, start));
    }
    segments.push(
      <mark key={start} className="bg-search-highlight text-inherit">
        {text.slice(start, end)}
      </mark>,
    );
    cursor = end;
  }
  if (segments.length === 0) {
    return text;
  }
  if (cursor < text.length) {
    segments.push(text.slice(cursor));
  }
  return segments;
}

/**
 * Wrap every match of `pattern` in `text` in a `<mark>` element. Returns
 * `text` unchanged when `pattern` is absent or does not match.
 */
export function highlightMatches(text: string, pattern?: RegExp): ReactNode {
  return highlightRanges(text, findMatchRanges(text, pattern));
}
