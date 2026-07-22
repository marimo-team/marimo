/* Copyright 2026 Marimo. All rights reserved. */
import { useMemo, useState } from "react";
import { assertNever } from "@/utils/assertNever";
import type { BulkAction, Option } from "./types";
import {
  deselectMatching,
  getBulkActions,
  getVisibleOptions,
  multiselectFilterFn,
  selectMatching,
} from "./utils";

/** cmdk-style relevance score for `(label, query)`; any positive score matches. */
type FilterFn = (label: string, query: string) => number;

interface UseSelectListBaseParams<V> {
  options: Array<Option<V>>;
  /** Cap on multi-select size. At the cap, picking another drops the oldest. */
  maxSelections?: number;
  /** Single-select only: re-picking the current value clears it to null. */
  allowSelectNone?: boolean;
  /** Match predicate over `(label, query)`; defaults to the strict word match. */
  filterFn?: FilterFn;
  /** Float the (frozen) selection to the top of the idle menu. */
  pinSelected?: boolean;
}

interface UseSelectListMultiParams<V> extends UseSelectListBaseParams<V> {
  multiple: true;
  value: V[] | null;
  onChange: (next: V[]) => void;
}

interface UseSelectListSingleParams<V> extends UseSelectListBaseParams<V> {
  multiple: false;
  value: V | null;
  onChange: (next: V | null) => void;
}

/** Implementation / wide signature for facades that forward a runtime `multiple`. */
interface UseSelectListImplParams<V> extends UseSelectListBaseParams<V> {
  multiple: boolean;
  value: V[] | V | null;
  onChange: (next: V[] | V | null) => void;
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
  /**
   * Renderable bulk rows for the current search/cap state, in display order.
   * Empty for single-select. Each entry carries its data (`enabled` or `items`)
   * and a `run` closure that applies it.
   */
  bulkActions: Array<BulkAction<V>>;
  /** Map a value back to its option label; falls back to `String(value)`. */
  labelOf: (value: V) => string;
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
    return options.filter((o) => filterFn(o.label, searchQuery) > 0);
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

  const { visibleOptions, pinnedCount } = useMemo(() => {
    if (searchQuery || !pinSelected) {
      return { visibleOptions: filteredOptions, pinnedCount: 0 };
    }
    return getVisibleOptions(options, pinnedSelection);
  }, [searchQuery, pinSelected, filteredOptions, options, pinnedSelection]);

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

/** Bulk-row specs paired with run closures; inert for single-select. */
function useBulk<V>({
  value,
  onChange,
  multiple,
  options,
  filteredOptions,
  searchQuery,
  maxSelections,
}: BulkParams<V>): { bulkActions: Array<BulkAction<V>> } {
  const bulkActions = useMemo<Array<BulkAction<V>>>(() => {
    if (!multiple) {
      return [];
    }
    const specs = getBulkActions({
      options,
      filteredOptions,
      value: asArray(value),
      searchQuery,
      maxSelections,
    });
    return specs.map((spec): BulkAction<V> => {
      switch (spec.kind) {
        case "select-all":
          return {
            ...spec,
            run: () =>
              onChange(
                selectMatching(
                  asArray(value),
                  options.filter((o) => !o.disabled).map((o) => o.value),
                ),
              ),
          };
        case "deselect-all":
          return { ...spec, run: () => onChange([]) };
        case "select-matching":
          return {
            ...spec,
            run: () =>
              onChange(
                selectMatching(
                  asArray(value),
                  spec.items.map((o) => o.value),
                ),
              ),
          };
        case "deselect-matching":
          return {
            ...spec,
            run: () =>
              onChange(
                deselectMatching(
                  asArray(value),
                  spec.items.map((o) => o.value),
                ),
              ),
          };
        default:
          return assertNever(spec);
      }
    });
  }, [
    multiple,
    options,
    filteredOptions,
    value,
    searchQuery,
    maxSelections,
    onChange,
  ]);

  return { bulkActions };
}

/**
 * Headless state for a searchable select list, shared across the multiselect,
 * dropdown, top-K filter, and custom Popover/Command facades. Composes search,
 * pinning/freeze, membership/toggle, and bulk actions behind one entry point.
 * Closing the menu clears the query; single-select `toggle` also dismisses.
 * Pinning and bulk rows are opt-in so single-select facades share only what
 * they need.
 */
export function useSelectList<V>(
  params: UseSelectListMultiParams<V>,
): UseSelectListResult<V>;
export function useSelectList<V>(
  params: UseSelectListSingleParams<V>,
): UseSelectListResult<V>;
/** Wide form for facades that forward a runtime `multiple` flag. */
export function useSelectList<V>(
  params: UseSelectListImplParams<V>,
): UseSelectListResult<V>;
export function useSelectList<V>({
  options,
  value,
  onChange,
  multiple,
  maxSelections,
  allowSelectNone,
  filterFn = multiselectFilterFn,
  pinSelected = false,
}: UseSelectListImplParams<V>): UseSelectListResult<V> {
  const selected = useMemo(() => new Set(asArray(value)), [value]);

  const labelByValue = useMemo(() => {
    const map = new Map<V, string>();
    for (const option of options) {
      map.set(option.value, option.label);
    }
    return map;
  }, [options]);
  const labelOf = (candidate: V): string =>
    labelByValue.get(candidate) ?? String(candidate);

  const {
    searchQuery,
    setSearchQuery: setSearchQueryState,
    filteredOptions,
  } = useSearch({ options, filterFn });

  const {
    open,
    setOpen: setOpenState,
    repin,
    visibleOptions,
    pinnedCount,
  } = usePinning({
    value,
    pinSelected,
    options,
    searchQuery,
    filteredOptions,
  });

  const { isChecked, toggle: toggleSelection } = useToggle({
    value,
    onChange,
    multiple,
    maxSelections,
    allowSelectNone,
    selected,
  });

  const { bulkActions } = useBulk({
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

  // Reset the query when the menu closes so reopen starts idle (and pinned).
  const setOpen = (nextOpen: boolean): void => {
    setOpenState(nextOpen);
    if (!nextOpen) {
      setSearchQueryState("");
    }
  };

  // Single-select menus dismiss on pick, matching Combobox. Multi stays open for
  // further toggles.
  const toggle = (candidate: V): void => {
    toggleSelection(candidate);
    if (!multiple) {
      setOpen(false);
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
    labelOf,
  };
}
