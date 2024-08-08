/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-empty-interface */
import { CSSProperties } from "react";
import { OnChangeFn, RowData } from "@tanstack/react-table";

// define types for column pinning's position
export type ColumnPinningPosition = false | "left" | "right";

// define types for column pinning's state
export interface ColumnPinningState {
  left?: string[];
  right?: string[];
}

// define types for column pinning's table state
export interface ColumnPinningTableState {
  columnPinning: ColumnPinningState;
}

// define types for column pinning's table options
export interface ColumnPinningOptions {
  enableColumnPinning?: boolean;
  onColumnPinningChange?: OnChangeFn<ColumnPinningState>;
}

export interface ColumnPinningInstance {
  // gets the column's pinning state
  getIsPinned?: () => ColumnPinningPosition;

  // gets if the column can be pinned
  getCanPin?: () => boolean;

  // gets the column's common pinning styles
  getCommonPinningStyles?: () => CSSProperties;

  // sets the column's pinning state
  setColumnPinning: (position?: ColumnPinningPosition) => void;

  // toggles the column's pinning state
  toggleColumnPinning: (position: ColumnPinningPosition) => void;
}

// Use declaration merging to add our new feature APIs
declare module "@tanstack/react-table" {
  interface TableState extends ColumnPinningTableState {}

  interface TableOptionsResolved<TData extends RowData>
    extends ColumnPinningOptions {}

  interface Column<TData extends RowData> extends ColumnPinningInstance {}
}
