/* Copyright 2024 Marimo. All rights reserved. */

import type { OnChangeFn, RowData } from "@tanstack/react-table";

export type ColumnWrappingState = Record<string, "nowrap" | "wrap" | undefined>;
export interface ColumnWrappingTableState {
  columnWrapping: ColumnWrappingState;
}

export interface ColumnWrappingOptions {
  enableColumnWrapping?: boolean;
  onColumnWrappingChange?: OnChangeFn<ColumnWrappingState>;
}

export interface ColumnWrappingInstance {
  toggleColumnWrapping: (value?: "nowrap" | "wrap") => void;
  getColumnWrapping?: () => "nowrap" | "wrap";
  getCanWrap?: () => boolean;
}

// Use declaration merging to add our new feature APIs
declare module "@tanstack/react-table" {
  interface TableState extends ColumnWrappingTableState {}

  interface TableOptionsResolved<TData extends RowData>
    extends ColumnWrappingOptions {}

  interface Column<TData extends RowData> extends ColumnWrappingInstance {}
}
