/* Copyright 2024 Marimo. All rights reserved. */
import {
  type TableFeature,
  type RowData,
  makeStateUpdater,
  type Table,
  type Column,
  type Updater,
} from "@tanstack/react-table";
import type {
  ColumnWrappingTableState,
  ColumnWrappingOptions,
  ColumnWrappingState,
} from "./types";

export const ColumnWrappingFeature: TableFeature = {
  getInitialState: (state): ColumnWrappingTableState => {
    return {
      columnWrapping: {},
      ...state,
    };
  },

  getDefaultOptions: <TData extends RowData>(
    table: Table<TData>,
  ): ColumnWrappingOptions => {
    return {
      enableColumnWrapping: true,
      onColumnWrappingChange: makeStateUpdater("columnWrapping", table),
    } as ColumnWrappingOptions;
  },

  createColumn: <TData extends RowData>(
    column: Column<TData>,
    table: Table<TData>,
  ) => {
    column.getColumnWrapping = () => {
      return table.getState().columnWrapping[column.id] || "nowrap";
    };

    column.getCanWrap = () => {
      return table.options.enableColumnWrapping ?? false;
    };

    column.toggleColumnWrapping = (value?: "nowrap" | "wrap") => {
      const safeUpdater: Updater<ColumnWrappingState> = (old) => {
        const prevValue = old[column.id] || "nowrap";
        if (value) {
          return {
            ...old,
            [column.id]: value,
          };
        }
        return {
          ...old,
          [column.id]: prevValue === "nowrap" ? "wrap" : "nowrap",
        };
      };
      table.options.onColumnWrappingChange?.(safeUpdater);
    };
  },
};
