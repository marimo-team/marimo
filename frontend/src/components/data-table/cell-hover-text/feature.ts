/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import type {
  Cell,
  Column,
  InitialTableState,
  Row,
  RowData,
  Table,
  TableFeature,
} from "@tanstack/react-table";
import { getStableRowId } from "../utils";
import type { CellHoverTextState, CellHoverTextTableState } from "./types";

function getRowId<TData>(row: Row<TData>): string {
  return getStableRowId(row) ?? row.id;
}

export const CellHoverTextFeature: TableFeature = {
  getInitialState: (state?: InitialTableState): CellHoverTextTableState => {
    return {
      ...state,
      cellHoverTexts: {} as CellHoverTextState,
    };
  },

  createCell: <TData extends RowData>(
    cell: Cell<TData, unknown>,
    column: Column<TData>,
    row: Row<TData>,
    table: Table<TData>,
  ) => {
    cell.getHoverTitle = () => {
      const state = table.getState().cellHoverTexts;
      const rowId = getRowId(row);
      return state?.[rowId]?.[column.id] ?? undefined;
    };
  },
};
