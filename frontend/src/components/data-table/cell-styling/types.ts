/* Copyright 2024 Marimo. All rights reserved. */

import type { RowData } from "@tanstack/react-table";

export type CellStyleState = Record<
  string,
  Record<string, React.CSSProperties>
>;

export interface CellStylingTableState {
  cellStyling: CellStyleState | undefined | null;
}

export interface CellStylingCell {
  /**
   * Returns additional styling for the cell.
   */
  getUserStyling?: () => React.CSSProperties;
}

// Use declaration merging to add our new feature APIs
declare module "@tanstack/react-table" {
  interface TableState extends CellStylingTableState {}

  interface Cell<TData extends RowData, TValue> extends CellStylingCell {}
}
