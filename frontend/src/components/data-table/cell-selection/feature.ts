/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import {
  type Table,
  type Cell,
  type TableFeature,
  type InitialTableState,
  type RowData,
  makeStateUpdater,
  type Column,
  type Row,
} from "@tanstack/react-table";

import { Functions } from "@/utils/functions";

import type {
  CellSelectionOptions,
  CellSelectionState,
  CellSelectionTableState,
} from "./types";
import { INDEX_COLUMN_NAME } from "../types";

function getRowId<TData>(row: Row<TData>): string {
  if (row && typeof row === "object" && INDEX_COLUMN_NAME in row) {
    return String(row[INDEX_COLUMN_NAME]);
  }
  return row.id;
}

export const CellSelectionFeature: TableFeature = {
  getInitialState: (state?: InitialTableState): CellSelectionTableState => {
    return {
      ...state,
      cellSelection: [] as CellSelectionState,
    };
  },

  getDefaultOptions: <TData extends RowData>(
    table: Table<TData>,
  ): CellSelectionOptions => ({
    onCellSelectionChange: makeStateUpdater("cellSelection", table),
    enableCellSelection: false,
  }),

  createTable: <TData>(table: Table<TData>): void => {
    table.setCellSelection = (updater) => {
      // TODO: can we access?
      // table._getRowId
      // check if pagination is active

      table.setState((tableState) => ({
        ...tableState,
        cellSelection: Functions.asUpdater(updater)(tableState.cellSelection),
      }));
      table.options.onCellSelectionChange?.(updater);
    };

    table.resetCellSelection = (defaultValue) => {
      table.setCellSelection(() => defaultValue ?? []);
    };

    table.getIsAllCellsSelected = () => {
      const state = table.getState().cellSelection ?? [];
      return (
        state.length === table.getRowCount() * table.getAllColumns().length
      );
    };

    table.getIsAllPageCellsSelected = () => false; // TODO: I don't quite have a notion of pages yet
  },

  createCell: <TData extends RowData>(
    cell: Cell<TData, unknown>,
    column: Column<TData>,
    row: Row<TData>,
    table: Table<TData>,
  ) => {
    cell.getIsSelected = () => {
      const state: CellSelectionState = table.getState().cellSelection ?? [];
      return state.some(
        (item) => item.rowId === getRowId(row) && item.columnName === column.id,
      );
    };

    cell.toggleSelected = (value?: boolean) => {
      const columnName = column.id;

      const currentIsSelected = cell.getIsSelected();
      const nextIsSelected = value !== undefined ? value : !currentIsSelected;
      const rowId = getRowId(row);
      console.log(
        `Should toggle cell: row id = ${rowId}, columnName = ${columnName}, value = ${value}, currently ${currentIsSelected}, next ${nextIsSelected}`,
      );

      if (nextIsSelected && !currentIsSelected) {
        // Add cell to selection
        if (table.options.enableMultiCellSelection) {
          table.setCellSelection((selectedCells) => [
            {
              rowId,
              columnName: columnName,
            },
            ...selectedCells,
          ]);
        } else {
          // This cell becomes the single selected cell
          table.setCellSelection((_) => [
            {
              rowId: rowId,
              columnName: columnName,
            },
          ]);
        }
      } else if (currentIsSelected && !nextIsSelected) {
        // Deselect cell from selection
        if (table.options.enableMultiCellSelection) {
          table.setCellSelection((selectedCells) =>
            selectedCells.filter(
              (c) => c.rowId !== rowId && c.columnName !== columnName,
            ),
          );
        } else {
          // Clear the selection
          table.setCellSelection((_) => []);
        }
      }
    };
  },
};
