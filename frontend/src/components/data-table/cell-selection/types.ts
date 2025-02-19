/* Copyright 2024 Marimo. All rights reserved. */
import type { OnChangeFn, RowData, Updater } from "@tanstack/react-table";

export type CellSelectionItem = { rowId: string; columnName: string };
export type CellSelectionState = CellSelectionItem[];
export type CellSelectionTableState = {
  cellSelection: CellSelectionState;
};

export interface CellSelectionOptions {
  enableCellSelection?: boolean;
  enableMultiCellSelection?: boolean;
  onCellSelectionChange?: OnChangeFn<CellSelectionState>; // | CellSelectionItem ???
}

export interface CellSelectionCell {
  /**
   * Returns whether or not the cell is selected.
   */
  getIsSelected: () => boolean;

  /**
   * Selects/deselects the cell.
   */
  toggleSelected: (value?: boolean) => void;
}

// These are additional properties add to the table instance in createTable
export interface CellSelectionInstance<TData extends RowData> {
  setCellSelection: (updater: Updater<CellSelectionState>) => void;
}

// Use declaration merging to add our new feature APIs
declare module "@tanstack/react-table" {
  interface TableState extends CellSelectionTableState {}

  interface TableOptionsResolved<TData extends RowData>
    extends CellSelectionOptions {}

  interface Table<TData extends RowData> extends CellSelectionInstance<TData> {}

  interface Cell<TData extends RowData, TValue> extends CellSelectionCell {}
}
