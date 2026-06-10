/* Copyright 2026 Marimo. All rights reserved. */
import { useMemo, useState } from "react";
import type { BulkActions, Option } from "./types";
import {
  deselectMatching,
  getBulkActions,
  getVisibleOptions,
  multiselectFilterFn,
  selectMatching,
} from "./utils";

type FilterFn = (label: string, query: string) => number;

interface UseSelectListParams<V> {
  options: Array<Option<V>>;
  /** Current selection: an array when `multiple`, otherwise a single value or null. */
  value: V[] | V | null;
  onChange: (next: V[] | V | null) => void;
  /** Multi-select when true; single-select (replace-on-pick) when false. */
  multiple: boolean;
  /** Cap on multi-select size. At the cap, picking another drops the oldest. */
  maxSelections?: number;
  /** Single-select only: re-picking the current value clears it to null. */
  allowSelectNone?: boolean;
  /** Match predicate over `(label, query)`; defaults to the strict word match. */
  filterFn?: FilterFn;
  /** Float the (frozen) selection to the top of the idle menu. */
  pinSelected?: boolean;
}

interface UseSelectListResult<V> {
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  open: boolean;
  setOpen: (open: boolean) => void;
  /** Filtered, and (when `pinSelected` and idle) selected-first ordered. */
  visibleOptions: Array<Option<V>>;
  /** Count of pinned options at the head of `visibleOptions` (0 unless pinned + idle). */
  pinnedCount: number;
  isChecked: (value: V) => boolean;
  toggle: (value: V) => void;
  /** Bulk-row config for the current search/cap state (empty for single-select). */
  bulkActions: BulkActions;
  /** Apply a bulk action: search-scoped additive when searching, all/none when idle. */
  runBulk: (kind: "select" | "deselect") => void;
}

function asArray<V>(value: V[] | V | null): V[] {
  if (value == null) {
    return [];
  }
  return Array.isArray(value) ? value : [value];
}

interface SearchParams<V> {
  options: Array<Option<V>>;
  filterFn: FilterFn;
}

/** Search query and the options that currently match it. */
function useSearch<V>({ options, filterFn }: SearchParams<V>): {
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  filteredOptions: Array<Option<V>>;
} {
  const [searchQuery, setSearchQuery] = useState("");
  const filteredOptions = useMemo(() => {
    if (!searchQuery) {
      return options;
    }
    return options.filter((o) => filterFn(o.label, searchQuery) === 1);
  }, [options, searchQuery, filterFn]);
  return { searchQuery, setSearchQuery, filteredOptions };
}

interface PinningParams<V> {
  value: V[] | V | null;
  pinSelected: boolean;
  options: Array<Option<V>>;
  searchQuery: string;
  filteredOptions: Array<Option<V>>;
}

/**
 * Open state plus the frozen selection snapshot that orders the idle menu. The
 * snapshot is retaken (`repin`) when the menu opens or the search clears, so a row
 * toggled mid-session keeps its place instead of jumping to the top under the cursor.
 */
function usePinning<V>({
  value,
  pinSelected,
  options,
  searchQuery,
  filteredOptions,
}: PinningParams<V>): {
  open: boolean;
  setOpen: (open: boolean) => void;
  repin: () => void;
  visibleOptions: Array<Option<V>>;
  pinnedCount: number;
} {
  const [open, setOpenState] = useState(false);
  const [pinnedSelection, setPinnedSelection] = useState<Set<V>>(
    () => new Set(asArray(value)),
  );

  const repin = (): void => setPinnedSelection(new Set(asArray(value)));

  const setOpen = (nextOpen: boolean): void => {
    setOpenState(nextOpen);
    if (nextOpen) {
      repin();
    }
  };

  const visibleOptions = useMemo(() => {
    if (searchQuery || !pinSelected) {
      return filteredOptions;
    }
    return getVisibleOptions(options, pinnedSelection);
  }, [searchQuery, pinSelected, filteredOptions, options, pinnedSelection]);

  const pinnedCount = useMemo(() => {
    if (searchQuery || !pinSelected) {
      return 0;
    }
    return options.filter((o) => pinnedSelection.has(o.value)).length;
  }, [searchQuery, pinSelected, options, pinnedSelection]);

  return { open, setOpen, repin, visibleOptions, pinnedCount };
}

interface ToggleParams<V> {
  value: V[] | V | null;
  onChange: (next: V[] | V | null) => void;
  multiple: boolean;
  maxSelections: number | undefined;
  allowSelectNone: boolean | undefined;
  selected: ReadonlySet<V>;
}

/** Membership test and the cap/cardinality-aware single-item toggle. */
function useToggle<V>({
  value,
  onChange,
  multiple,
  maxSelections,
  allowSelectNone,
  selected,
}: ToggleParams<V>): {
  isChecked: (value: V) => boolean;
  toggle: (value: V) => void;
} {
  const isChecked = (candidate: V): boolean => selected.has(candidate);

  const toggle = (candidate: V): void => {
    if (!multiple) {
      if (allowSelectNone && value === candidate) {
        onChange(null);
        return;
      }
      onChange(candidate);
      return;
    }

    const current = asArray(value);
    if (selected.has(candidate)) {
      onChange(current.filter((v) => v !== candidate));
      return;
    }

    let next = [...current, candidate];
    if (maxSelections != null && next.length > maxSelections) {
      next = next.slice(-maxSelections);
    }
    onChange(next);
  };

  return { isChecked, toggle };
}

interface BulkParams<V> {
  value: V[] | V | null;
  onChange: (next: V[] | V | null) => void;
  multiple: boolean;
  options: Array<Option<V>>;
  filteredOptions: Array<Option<V>>;
  searchQuery: string;
  maxSelections: number | undefined;
}

/** Bulk-row config and execution; inert for single-select. */
function useBulk<V>({
  value,
  onChange,
  multiple,
  options,
  filteredOptions,
  searchQuery,
  maxSelections,
}: BulkParams<V>): {
  bulkActions: BulkActions;
  runBulk: (kind: "select" | "deselect") => void;
} {
  const bulkActions = useMemo<BulkActions>(() => {
    if (!multiple) {
      return {};
    }
    return getBulkActions({
      options,
      filteredOptions,
      value: asArray(value),
      searchQuery,
      maxSelections,
    });
  }, [multiple, options, filteredOptions, value, searchQuery, maxSelections]);

  const runBulk = (kind: "select" | "deselect"): void => {
    const current = asArray(value);
    const matches = filteredOptions.map((o) => o.value);
    if (kind === "select") {
      onChange(
        searchQuery
          ? selectMatching(current, matches)
          : options.map((o) => o.value),
      );
    } else {
      onChange(searchQuery ? deselectMatching(current, matches) : []);
    }
  };

  return { bulkActions, runBulk };
}

/**
 * Headless state for a searchable select list, shared across the multiselect,
 * dropdown, and top-K filter facades. Composes four focused concerns — search,
 * pinning/freeze, membership/toggle, and bulk actions — behind one entry point.
 * Pinning and bulk rows are opt-in so the single-select and top-K facades share
 * only what they need.
 */
export function useSelectList<V>({
  options,
  value,
  onChange,
  multiple,
  maxSelections,
  allowSelectNone,
  filterFn = multiselectFilterFn,
  pinSelected = false,
}: UseSelectListParams<V>): UseSelectListResult<V> {
  const selected = useMemo(() => new Set(asArray(value)), [value]);

  const {
    searchQuery,
    setSearchQuery: setSearchQueryState,
    filteredOptions,
  } = useSearch({ options, filterFn });

  const { open, setOpen, repin, visibleOptions, pinnedCount } = usePinning({
    value,
    pinSelected,
    options,
    searchQuery,
    filteredOptions,
  });

  const { isChecked, toggle } = useToggle({
    value,
    onChange,
    multiple,
    maxSelections,
    allowSelectNone,
    selected,
  });

  const { bulkActions, runBulk } = useBulk({
    value,
    onChange,
    multiple,
    options,
    filteredOptions,
    searchQuery,
    maxSelections,
  });

  const setSearchQuery = (query: string): void => {
    setSearchQueryState(query);
    if (query === "") {
      repin();
    }
  };

  return {
    searchQuery,
    setSearchQuery,
    open,
    setOpen,
    visibleOptions,
    pinnedCount,
    isChecked,
    toggle,
    bulkActions,
    runBulk,
  };
}
