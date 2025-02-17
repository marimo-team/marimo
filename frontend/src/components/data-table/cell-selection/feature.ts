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
      console.log(
        "table.setCellSelection",
        table.options.onCellSelectionChange,
      );
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
        (item) => item.row === cell.row.id && item.column === cell.column.id,
      );
    };

    cell.toggleSelected = (value?: boolean) => {
      console.log(`Should toggle cell ${row.id} ${cell.id} ${value}`);
      table.setCellSelection((_) => [
        {
          row: row.id,
          column: column.id,
        },
      ]);
    };
  },
};
