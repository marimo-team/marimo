/* Copyright 2026 Marimo. All rights reserved. */

import {
  type ColumnDef,
  getCoreRowModel,
  type Table,
  useReactTable,
} from "@tanstack/react-table";
import { renderHook } from "@testing-library/react";
import { vi } from "vitest";
import type { FilterType } from "../filters";

export interface FilterColumnSpec {
  id: string;
  filterType?: FilterType;
  dtype?: string;
}

export interface FilterTestHarness {
  table: Table<unknown>;
  setColumnFilters: ReturnType<typeof vi.fn>;
}

export function buildFilterTestTable(
  specs: FilterColumnSpec[],
): FilterTestHarness {
  const setColumnFilters = vi.fn();
  const columns: Array<ColumnDef<unknown>> = specs.map((spec) => ({
    id: spec.id,
    accessorFn: () => undefined,
    header: spec.id,
    meta: {
      ...(spec.filterType !== undefined ? { filterType: spec.filterType } : {}),
      ...(spec.dtype !== undefined ? { dtype: spec.dtype } : {}),
    },
  }));
  const { result } = renderHook(() =>
    useReactTable<unknown>({
      data: [],
      columns,
      locale: "en-US",
      getCoreRowModel: getCoreRowModel(),
      onColumnFiltersChange: setColumnFilters,
    }),
  );
  return { table: result.current, setColumnFilters };
}
