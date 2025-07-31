/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-empty-interface */

import type { OnChangeFn, RowData } from "@tanstack/react-table";
import type { DataType } from "@/core/kernel/messages";

// define all format options
export const formatOptions = {
  date: ["Date", "Datetime", "Time"],
  datetime: ["Date", "Datetime", "Time"],
  time: [],
  integer: ["Auto", "Percent", "Scientific", "Engineering", "Integer"],
  number: ["Auto", "Percent", "Scientific", "Engineering", "Integer"],
  string: ["Uppercase", "Lowercase", "Capitalize", "Title"],
  boolean: ["Yes/No", "On/Off"],
  unknown: [],
} as const satisfies Record<DataType, string[]>;

// define types for format options
export type FormatOptions = (typeof formatOptions)[keyof typeof formatOptions];
export type FormatOption = FormatOptions[number];

// define types for column formatting's custom state
export type ColumnFormattingState = Record<string, FormatOption | undefined>;
export interface ColumnFormattingTableState {
  columnFormatting: ColumnFormattingState;
}

// define types for column formatting's table options
export interface ColumnFormattingOptions {
  enableColumnFormatting?: boolean;
  onColumnFormattingChange?: OnChangeFn<ColumnFormattingState>;
}

// define types for column formatting's table APIs
export interface ColumnFormattingInstance {
  setColumnFormatting: (value?: FormatOption) => void;
  getColumnFormatting?: () => FormatOption | undefined;
  getCanFormat?: () => boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  applyColumnFormatting: (value: any) => any;
}

// Use declaration merging to add APIs and state types
// to TanStack Table's existing types.
declare module "@tanstack/react-table" {
  //merge column formatting's state with the existing table state
  interface TableState extends ColumnFormattingTableState {}
  //merge column formatting's options with the existing table options
  interface TableOptionsResolved<TData extends RowData>
    extends ColumnFormattingOptions {}
  //merge column formatting's instance APIs with the existing table instance APIs
  interface Column<TData extends RowData> extends ColumnFormattingInstance {}
}
