/* Copyright 2024 Marimo. All rights reserved. */

/**
 * We override the default filter function which focuses on sorting by relevance with a fuzzy-match,
 * instead of filtering out.
 * The default filter function is `command-score`.
 *
 * Our filter function only matches if all words in the value are present in the option.
 * This is more strict than the default, but more lenient than an exact match.
 *
 * Examples:
 * - "foo bar" matches "foo bar"
 * - "bar foo" matches "foo bar"
 * - "foob" does not matches "foo bar"
 */
export function multiselectFilterFn(option: string, value: string): number {
  const words = value.split(/\s+/);
  const match = words.every((word) =>
    option.toLowerCase().includes(word.toLowerCase()),
  );
  return match ? 1 : 0;
}
