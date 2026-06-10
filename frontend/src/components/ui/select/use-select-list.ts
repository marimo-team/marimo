/* Copyright 2026 Marimo. All rights reserved. */
import { useMemo, useState } from "react";
import type { Option } from "./types";
import { multiselectFilterFn } from "./utils";

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
}

interface UseSelectListResult<V> {
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  open: boolean;
  setOpen: (open: boolean) => void;
  visibleOptions: Array<Option<V>>;
  isChecked: (value: V) => boolean;
  toggle: (value: V) => void;
}

function asArray<V>(value: V[] | V | null): V[] {
  if (value == null) {
    return [];
  }
  return Array.isArray(value) ? value : [value];
}

/**
 * Headless state for a searchable select list, shared across the multiselect,
 * dropdown, and top-K filter facades. Owns search and open state, the filtered
 * `visibleOptions`, membership (`isChecked`), and a `toggle` that absorbs the
 * single/multi cardinality and the `maxSelections` cap so facades don't repeat
 * that policy.
 */
export function useSelectList<V>({
  options,
  value,
  onChange,
  multiple,
  maxSelections,
  allowSelectNone,
  filterFn = multiselectFilterFn,
}: UseSelectListParams<V>): UseSelectListResult<V> {
  const [searchQuery, setSearchQuery] = useState("");
  const [open, setOpen] = useState(false);

  const selected = useMemo(() => new Set(asArray(value)), [value]);

  const visibleOptions = useMemo(() => {
    if (!searchQuery) {
      return options;
    }
    return options.filter(
      (option) => filterFn(option.label, searchQuery) === 1,
    );
  }, [options, searchQuery, filterFn]);

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

  return {
    searchQuery,
    setSearchQuery,
    open,
    setOpen,
    visibleOptions,
    isChecked,
    toggle,
  };
}
