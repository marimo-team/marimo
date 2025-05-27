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

import type { CellStyleState, CellStylingTableState } from "./types";
import { getStableRowId } from "../utils";

function getRowId<TData>(row: Row<TData>): string {
  return getStableRowId(row) ?? row.id;
}

export const CellStylingFeature: TableFeature = {
  getInitialState: (state?: InitialTableState): CellStylingTableState => {
    return {
      ...state,
      cellStyling: {} as CellStyleState,
    };
  },

  createCell: <TData extends RowData>(
    cell: Cell<TData, unknown>,
    column: Column<TData>,
    row: Row<TData>,
    table: Table<TData>,
  ) => {
    cell.getUserStyling = () => {
      const state = table.getState().cellStyling;
      const rowId = getRowId(row);
      return state?.[rowId]?.[column.id] || {};
    };
  },
};
