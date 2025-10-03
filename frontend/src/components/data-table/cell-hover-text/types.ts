/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-empty-interface */

import type { RowData } from "@tanstack/react-table";

export type CellHoverTextState = Record<string, Record<string, string | null>>;

export interface CellHoverTextTableState {
  cellHoverTexts: CellHoverTextState;
}

export interface CellHoverTextCell {
  /**
   * Returns precomputed hover text for the cell, if any.
   */
  getHoverTitle?: () => string | undefined | null;
}

// Use declaration merging to add our new feature APIs
declare module "@tanstack/react-table" {
  interface TableState extends CellHoverTextTableState {}

  interface Cell<TData extends RowData, TValue> extends CellHoverTextCell {}
}
