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

export function getShowOnlyVisibility<TData>(
  table: Table<TData>,
  columnIds: string[],
): VisibilityState {
  const showOnlySet = new Set(columnIds);
  const visibility: VisibilityState = {};

  for (const column of table.getAllLeafColumns()) {
    if (!column.getCanHide()) {
      continue;
    }
    visibility[column.id] = showOnlySet.has(column.id);
  }

  return visibility;
}

export function applyShowOnlyColumns<TData>(
  table: Table<TData>,
  columnIds: string[],
): void {
  table.setColumnVisibility((previous) => ({
    ...previous,
    ...getShowOnlyVisibility(table, columnIds),
  }));
}

export interface ShowOnlyColumnState {
  visibleHideableColumnIds: readonly string[];
  hideableColumnIdSet: ReadonlySet<string>;
}

export function getShowOnlyColumnState<TData>(
  table: Table<TData>,
): ShowOnlyColumnState {
  const hideableIds: string[] = [];
  const visibleHideableColumnIds: string[] = [];

  for (const column of table.getAllLeafColumns()) {
    if (!column.getCanHide()) {
      continue;
    }
    hideableIds.push(column.id);
    if (column.getIsVisible()) {
      visibleHideableColumnIds.push(column.id);
    }
  }

  return {
    visibleHideableColumnIds,
    hideableColumnIdSet: new Set(hideableIds),
  };
}

export function isShowingOnlyColumns(
  state: ShowOnlyColumnState,
  columnIds: readonly string[],
): boolean {
  const targetIds = new Set(
    columnIds.filter((id) => state.hideableColumnIdSet.has(id)),
  );

  if (state.visibleHideableColumnIds.length !== targetIds.size) {
    return false;
  }

  return state.visibleHideableColumnIds.every((id) => targetIds.has(id));
}

export function isShowingOnly<TData>(
  table: Table<TData>,
  columnIds: string[],
): boolean {
  return isShowingOnlyColumns(getShowOnlyColumnState(table), columnIds);
}
