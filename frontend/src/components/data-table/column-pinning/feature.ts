/* Copyright 2024 Marimo. All rights reserved. */
import {
  Column,
  ColumnPinningOptions,
  ColumnPinningState,
  makeStateUpdater,
  RowData,
  Table,
  TableFeature,
  Updater,
} from "@tanstack/react-table";
import { ColumnPinningPosition, ColumnPinningTableState } from "./types";

export const ColumnPinningFeature: TableFeature = {
  getInitialState: (state): ColumnPinningTableState => {
    return {
      columnPinning: {
        ...state,
        left: [],
        right: [],
      },
    };
  },

  getDefaultOptions: <TData extends RowData>(
    table: Table<TData>,
  ): ColumnPinningOptions => {
    return {
      enableColumnPinning: true,
      onColumnPinningChange: makeStateUpdater("columnPinning", table),
    } as ColumnPinningOptions;
  },

  createColumn: <TData extends RowData>(
    column: Column<TData>,
    table: Table<TData>,
  ) => {
    column.getIsPinned = () => {
      const leftPinned = table
        .getState()
        .columnPinning.left?.includes(column.id);
      const rightPinned = table
        .getState()
        .columnPinning.right?.includes(column.id);
      return (leftPinned && "left") || (rightPinned && "right") || false;
    };

    column.getCanPin = () => {
      return table.options.enableColumnPinning ?? false;
    };

    column.pin = (position: ColumnPinningPosition) => {
      const safeUpdater: Updater<ColumnPinningState> = (prevState) => {
        const newState = prevState;

        if (!newState.left) {
          newState.left = [];
        }

        if (prevState.left != null && position === false) {
          newState.left = prevState.left.filter((id) => id !== column.id);
        } else {
          newState.left.push(column.id);
        }

        return newState;
      };
      table.options.onColumnPinningChange?.(safeUpdater);
    };
  },
};
