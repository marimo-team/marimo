/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-empty-interface */
import type { RowData, Updater } from "@tanstack/react-table";

export interface CellHeatmapTableState {
  columnHeatmap: Record<string, boolean>;
  cachedMinValue?: number | null;
  cachedMaxValue?: number | null;
}

export interface CellHeatmapOptions {
  enableCellHeatmap?: boolean;
  onGlobalHeatmapChange?: (updater: Updater<boolean>) => void;
  onColumnHeatmapChange?: (updater: Updater<Record<string, boolean>>) => void;
}

export interface CellHeatmapState {
  global: boolean;
  columns: Record<string, boolean>;
}

// Use declaration merging to add our new feature APIs
declare module "@tanstack/react-table" {
  interface TableState extends CellHeatmapTableState {}
  interface InitialTableState extends CellHeatmapTableState {}

  interface TableOptionsResolved<TData extends RowData>
    extends CellHeatmapOptions {}

  interface Table<TData extends RowData> {
    getGlobalHeatmap?: () => boolean;
    toggleGlobalHeatmap?: (value?: boolean) => void;
  }

  interface Column<TData extends RowData> {
    getCellHeatmapColor?: (cellValue: unknown) => string;
    toggleColumnHeatmap?: (value?: boolean) => void;
    getIsColumnHeatmapEnabled?: () => boolean;
  }
}
