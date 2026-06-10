/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Override cmdk's relevance-sorting filter with a stricter membership test: an
 * option matches only when every whitespace-separated query word appears in it
 * (case-insensitive), in any order. More lenient than exact match, stricter than
 * fuzzy.
 *
 * Examples:
 * - "foo bar" matches "foo bar"
 * - "bar foo" matches "foo bar"
 * - "foob" does not match "foo bar"
 */
export function multiselectFilterFn(option: string, value: string): number {
  const words = value.split(/\s+/);
  const match = words.every((word) =>
    option.toLowerCase().includes(word.toLowerCase()),
  );
  return match ? 1 : 0;
}

/** Union: append the not-yet-selected members of `toAdd`, preserving order. */
export function selectMatching<V>(selected: V[], toAdd: V[]): V[] {
  const set = new Set(selected);
  return [...set, ...toAdd.filter((v) => !set.has(v))];
}

/** Difference: drop every member of `toRemove` from `selected`. */
export function deselectMatching<V>(selected: V[], toRemove: V[]): V[] {
  const set = new Set(toRemove);
  return selected.filter((v) => !set.has(v));
}
