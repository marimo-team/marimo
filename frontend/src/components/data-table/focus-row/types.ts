/* Copyright 2024 Marimo. All rights reserved. */

import type { OnChangeFn, RowData } from "@tanstack/react-table";

// define types for feature's custom state
export type FocusRowState = number;
export interface FocusRowTableState {
  focusedRowIdx: FocusRowState;
}

// define types for feature's table options
export interface FocusRowOptions {
  enableFocusRow?: boolean;
  onFocusRowChange?: OnChangeFn<FocusRowState>;
}

// Define types for feature's table APIs
export interface FocusRowInstance {
  focusRow?: (rowIdx: FocusRowState) => void;
  getFocusedRowIdx?: () => FocusRowState;
}

// Use declaration merging to add feature APIs to TanStack Table's existing types
declare module "@tanstack/react-table" {
  interface TableState extends FocusRowTableState {}

  interface TableOptionsResolved<TData extends RowData>
    extends FocusRowOptions {}

  interface Row<TData extends RowData> extends FocusRowInstance {}
}
