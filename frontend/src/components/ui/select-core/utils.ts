/* Copyright 2026 Marimo. All rights reserved. */
import type { BulkActionSpec, Option } from "./types";

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

/**
 * Order options for the idle (no active search) menu: pinned selections first in
 * pin insertion order (so a freshly added selection appears after earlier ones),
 * then everything else in option order. `pinnedSelection` is a frozen snapshot
 * taken when the menu opens, so toggling an item does not reorder the list under
 * the cursor. Returns the count of pinned options alongside the list so callers
 * don't have to re-scan to find where the pinned block ends.
 */
export function getVisibleOptions<V>(
  options: Array<Option<V>>,
  pinnedSelection: ReadonlySet<V>,
): { visibleOptions: Array<Option<V>>; pinnedCount: number } {
  const byValue = new Map(options.map((o) => [o.value, o] as const));
  const pinned: Array<Option<V>> = [];
  for (const value of pinnedSelection) {
    const option = byValue.get(value);
    if (option) {
      pinned.push(option);
    }
  }
  const rest = options.filter((o) => !pinnedSelection.has(o.value));
  return { visibleOptions: [...pinned, ...rest], pinnedCount: pinned.length };
}

/**
 * Decide which bulk rows the menu shows for the current search/cap state.
 *
 * When searching, the select-side spec carries the unselected matches and the
 * deselect-side spec carries the selected matches (each omitted when empty).
 * When idle, the spec is just `select-all` / `deselect-all` with an `enabled`
 * flag for the disabled-but-visible state. `maxSelections` hides the select-
 * side everywhere (a bulk select could exceed the cap); `maxSelections === 1`
 * suppresses bulk rows entirely. Returns `[]` when bulk rows shouldn't show.
 *
 * Specs come in select-then-deselect order so the facade can render them as-is.
 */
export function getBulkActions<V>(params: {
  options: Array<Option<V>>;
  filteredOptions: Array<Option<V>>;
  value: V[];
  searchQuery: string;
  maxSelections: number | undefined;
}): Array<BulkActionSpec<V>> {
  const { options, filteredOptions, value, searchQuery, maxSelections } =
    params;

  if (options.length <= 2 || maxSelections === 1) {
    return [];
  }

  const capped = maxSelections != null;
  const specs: Array<BulkActionSpec<V>> = [];

  if (searchQuery !== "") {
    if (filteredOptions.length === 0) {
      return [];
    }
    const selected = new Set(value);
    const selectedMatches: Array<Option<V>> = [];
    const unselectedMatches: Array<Option<V>> = [];
    for (const option of filteredOptions) {
      (selected.has(option.value) ? selectedMatches : unselectedMatches).push(
        option,
      );
    }
    if (!capped && unselectedMatches.length > 0) {
      specs.push({ kind: "select-matching", items: unselectedMatches });
    }
    if (selectedMatches.length > 0) {
      specs.push({ kind: "deselect-matching", items: selectedMatches });
    }
    return specs;
  }

  if (!capped) {
    specs.push({
      kind: "select-all",
      enabled: value.length < options.length,
    });
  }
  specs.push({ kind: "deselect-all", enabled: value.length > 0 });
  return specs;
}
