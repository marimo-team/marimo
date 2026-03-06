/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Split a string into lowercase words (letters/digits only).
 */
function words(s: string): string[] {
  return s.toLowerCase().match(/[a-z\d]+/g) || [];
}

/**
 * Escape special regex characters.
 */
function escapeRegExp(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Returns true when every word in `needle` is a prefix of at least one word
 * in one of the `haystacks`.
 *
 * Examples:
 *   smartMatch("run", "Run cell")               // true  – "run" prefixes "run"
 *   smartMatch("exe", ["Run", "execute start"])  // true  – "exe" prefixes "execute"
 *   smartMatch("xyz", "Run cell")                // false
 */
export function smartMatch(
  needle: string,
  haystackOrHaystacks: string | Array<string | null | undefined>,
): boolean {
  const needleWords = words(needle);
  if (needleWords.length === 0) {
    return true; // empty search matches everything
  }

  const haystacks = Array.isArray(haystackOrHaystacks)
    ? haystackOrHaystacks
    : [haystackOrHaystacks];

  // Collect all words from all haystacks
  const haystackWords: string[] = [];
  for (const h of haystacks) {
    if (h) {
      haystackWords.push(...words(h));
    }
  }

  // Every needle word must be a prefix of at least one haystack word
  return needleWords.every((nw) => {
    return haystackWords.some((hw) => hw.startsWith(nw));
  });
}

/**
 * cmdk-compatible filter function.
 * Returns 1 for a value match, 0.8 for a keyword-only match, 0 for no match.
 */
export function smartMatchFilter(
  value: string,
  search: string,
  keywords?: string[],
): number {
  if (smartMatch(search, value)) {
    return 1;
  }
  if (keywords && smartMatch(search, keywords)) {
    return 0.8;
  }
  return 0;
}
