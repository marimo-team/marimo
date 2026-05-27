/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import { useInternalStateWithSync } from "@/hooks/useInternalStateWithSync";
import type { Table, VisibilityState } from "@tanstack/react-table";
import { dequal as isDeepEqual } from "dequal";
import type React from "react";

interface UseColumnVisibilityResult {
  columnVisibility: VisibilityState;
  setColumnVisibility: React.Dispatch<React.SetStateAction<VisibilityState>>;
}

export function useColumnVisibility(
  hiddenColumns?: string[],
): UseColumnVisibilityResult {
  const [columnVisibility, setColumnVisibility] =
    useInternalStateWithSync<VisibilityState>(
      Object.fromEntries((hiddenColumns ?? []).map((c) => [c, false])),
      isDeepEqual,
    );

  return { columnVisibility, setColumnVisibility };
}

interface ColumnVisibilityCounts {
  total: number;
  visible: number;
  hidden: number;
}

export function getUserColumnVisibilityCounts<TData>(
  table: Table<TData>,
): ColumnVisibilityCounts {
  const userColumns = table.getAllLeafColumns().filter((c) => c.getCanHide());
  const visible = userColumns.filter((c) => c.getIsVisible()).length;
  return {
    total: userColumns.length,
    visible,
    hidden: userColumns.length - visible,
  };
}

// When columns are clipped server-side, the TanStack instance only holds the
// rendered subset, so visible/hidden math must use that subset's total. The
// dataset-wide value is still correct for the no-hidden "N columns" label.
export function getColumnCountForDisplay<TData>(
  table: Table<TData>,
  datasetTotalColumns: number,
): { totalColumns: number; hiddenColumns: number } {
  const counts = getUserColumnVisibilityCounts(table);
  return {
    totalColumns: counts.hidden > 0 ? counts.total : datasetTotalColumns,
    hiddenColumns: counts.hidden,
  };
}
