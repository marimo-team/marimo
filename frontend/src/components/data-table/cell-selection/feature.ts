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
  },
  //   getCellSelection: () => table.getState().cellSelection ?? [],

  //   setCellSelection: (updater: Updater<CellSelectionState>) => {
  //     const newState =
  //       typeof updater === 'function'
  //         ? updater(table.getState().cellSelection ?? [])
  //         : updater
  //     table.options.onCellSelectionChange?.(newState)
  //   },

  //   isCellSelected: (rowId: string, columnId: string) => {
  //     const state = table.getState().cellSelection ?? []
  //     return state.some(item => item.row === rowId && item.column === columnId)
  //   },

  //   toggleCellSelected: (rowId: string, columnId: string, value?: boolean) => {
  //     table.setCellSelection(old => {
  //       const exists = old.some(item => item.row === rowId && item.column === columnId)
  //       let newState: CellSelectionState
  //       if (value === undefined) {
  //         newState = exists
  //           ? old.filter(item => !(item.row === rowId && item.column === columnId))
  //           : [...old, { row: rowId, column: columnId }]
  //       } else if (value) {
  //         newState = exists ? old : [...old, { row: rowId, column: columnId }]
  //       } else {
  //         newState = exists
  //           ? old.filter(item => !(item.row === rowId && item.column === columnId))
  //           : old
  //       }
  //       return newState
  //     })
  //   },

  //   getSelectedCellModel: () => {
  //     const cellSelection = table.getState().cellSelection ?? []
  //     return cellSelection
  //       .map(item => {
  //         const row = table.getRow(item.row)
  //         const column = table.getAllLeafColumns().find(col => col.id === item.column)
  //         return { row, column }
  //       })
  //       .filter(item => item.row && item.column)
  //   },
  // }),

  createCell: <TData extends RowData>(
    cell: Cell<TData, unknown>,
    column: Column<TData>,
    row: Row<TData>,
    table: Table<TData>,
  ) => {
    cell.getIsSelected = () => {
      const state: CellSelectionState = table.getState().cellSelection ?? [];
      return state.some(
        (item) => item.rowId === cell.row.id && item.columnName === column.id,
      );
    };

    cell.toggleSelected = (value?: boolean) => {
      const columnName = column.id;

      const currentIsSelected = cell.getIsSelected();
      const nextIsSelected = value !== undefined ? value : !currentIsSelected;
      console.log(
        `Should toggle cell: row id = ${row.id}, columnName = ${columnName}, value = ${value}, currently ${currentIsSelected}, next ${nextIsSelected}`,
      );

      if (nextIsSelected && !currentIsSelected) {
        // Add cell to selection
        if (table.options.enableMultiCellSelection) {
          table.setCellSelection((selectedCells) => [
            {
              rowId: row.id,
              columnName: columnName,
            },
            ...selectedCells,
          ]);
        } else {
          // This cell becomes the single selected cell
          table.setCellSelection((_) => [
            {
              rowId: row.id,
              columnName: columnName,
            },
          ]);
        }
      } else if (currentIsSelected && !nextIsSelected) {
        // Deselect cell from selection
        if (table.options.enableMultiCellSelection) {
          table.setCellSelection((selectedCells) =>
            selectedCells.filter(
              (c) => c.rowId !== row.id && c.columnName !== columnName,
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
