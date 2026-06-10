/* Copyright 2026 Marimo. All rights reserved. */
import type { BulkActions, Option } from "./types";

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
 * option order, then everything else in option order. `pinnedSelection` is a frozen
 * snapshot taken when the menu opens, so toggling an item does not reorder the list
 * under the cursor.
 */
export function getVisibleOptions<V>(
  options: Array<Option<V>>,
  pinnedSelection: ReadonlySet<V>,
): Array<Option<V>> {
  const pinned: Array<Option<V>> = [];
  const rest: Array<Option<V>> = [];
  for (const option of options) {
    if (pinnedSelection.has(option.value)) {
      pinned.push(option);
    } else {
      rest.push(option);
    }
  }
  return [...pinned, ...rest];
}

/**
 * Decide which bulk rows the menu shows and how they are labeled.
 *
 * When the search box has text the rows act on the matching (filtered) options and
 * their counts reflect actionable items: select = matches not yet chosen, deselect =
 * matches currently chosen. With no search they act on every option ("Select all" /
 * "Deselect all"). The select-side row is hidden whenever `maxSelections` is set,
 * since a bulk select could exceed the cap; a single-selection list shows no bulk
 * rows at all.
 */
export function getBulkActions<V>(params: {
  options: Array<Option<V>>;
  filteredOptions: Array<Option<V>>;
  value: V[];
  searchQuery: string;
  maxSelections: number | undefined;
}): BulkActions {
  const { options, filteredOptions, value, searchQuery, maxSelections } =
    params;

  // if only one option OR single select mode, no bulk actions
  if (options.length <= 2 || maxSelections === 1) {
    return {};
  }

  const capped = maxSelections != null;

  if (searchQuery !== "") {
    if (filteredOptions.length === 0) {
      return {};
    }
    const selected = new Set(value);
    const selectedMatches = filteredOptions.filter((o) =>
      selected.has(o.value),
    ).length;
    const unselectedMatches = filteredOptions.length - selectedMatches;
    const actions: BulkActions = {
      deselect: {
        label: `Deselect ${selectedMatches} matching`,
        enabled: selectedMatches > 0,
      },
    };
    if (!capped) {
      actions.select = {
        label: `Select ${unselectedMatches} matching`,
        enabled: unselectedMatches > 0,
      };
    }
    return actions;
  }

  // in multiselect we always have a deselect all
  const actions: BulkActions = {
    deselect: { label: "Deselect all", enabled: value.length > 0 },
  };

  // if we have no cap on selection, allow select all
  if (!capped) {
    actions.select = {
      label: "Select all",
      enabled: value.length < options.length,
    };
  }
  return actions;
}
