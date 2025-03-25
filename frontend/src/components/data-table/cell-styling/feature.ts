/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import type {
  Table,
  Cell,
  Column,
  Row,
  RowData,
  TableFeature,
  InitialTableState,
} from "@tanstack/react-table";

import type { CellStylingTableState } from "./types";

export const CellStylingFeature: TableFeature = {
  getInitialState: (state?: InitialTableState): CellStylingTableState => {
    return {
      ...state,
      cellStyling: [] as React.CSSProperties[][],
    };
  },

  createCell: <TData extends RowData>(
    cell: Cell<TData, unknown>,
    column: Column<TData>,
    row: Row<TData>,
    table: Table<TData>,
  ) => {
    const state = table.getState().cellStyling;

    cell.getUserStyling = () => {
      if (row.index < state.length) {
        const rowStyling = state[row.index];
        const columnIdx = column.getIndex();
        if (columnIdx < rowStyling.length) {
          return rowStyling[columnIdx];
        }
      }

      return {};
    };
  },
};
