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
import { getStableRowId } from "../utils";

function getRowId<TData>(row: Row<TData>): string {
  return getStableRowId(row) ?? row.id;
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
      if (table.setCellSelection) {
        table.setCellSelection(() => defaultValue ?? []);
      }
    };
  },

  createCell: <TData extends RowData>(
    cell: Cell<TData, unknown>,
    column: Column<TData>,
    row: Row<TData>,
    table: Table<TData>,
  ) => {
    // This could be a performance bottleneck if we have a lot of cells.
    // (for each cell, for each selected cell), which is O(n^2)
    // Perhaps consider using datastructure mentioned in https://github.com/marimo-team/marimo/pull/3725/files#r1974362428
    cell.getIsSelected = () => {
      const state: CellSelectionState = table.getState().cellSelection ?? [];
      return state.some(
        (item) => item.rowId === getRowId(row) && item.columnName === column.id,
      );
    };

    cell.toggleSelected = (value?: boolean) => {
      if (!table.setCellSelection) {
        return;
      }

      const columnName = column.id;

      const currentIsSelected = cell.getIsSelected?.() || false;
      const nextIsSelected = value === undefined ? !currentIsSelected : value;
      const rowId = getRowId(row);

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
              (c) => !(c.rowId === rowId && c.columnName === columnName),
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
