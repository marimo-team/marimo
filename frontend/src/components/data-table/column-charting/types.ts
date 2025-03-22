/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-empty-interface */
import type { RowData } from "@tanstack/react-table";

// biome-ignore lint/suspicious/noEmptyInterface: <explanation>
export interface ColumnChartingTableState {}

export interface ColumnChartingOptions {
  enableColumnCharting: boolean;
  tableName: string;
}

export interface ColumnChartingInstance {
  renderChartMenuItems?: () => React.ReactNode;
}

// Use declaration merging to add our new feature APIs
declare module "@tanstack/react-table" {
  interface TableState extends ColumnChartingTableState {}

  interface TableOptionsResolved<TData extends RowData>
    extends ColumnChartingOptions {}

  interface Column<TData extends RowData> extends ColumnChartingInstance {}
}
