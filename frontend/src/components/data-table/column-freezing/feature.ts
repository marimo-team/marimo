/* Copyright 2024 Marimo. All rights reserved. */
import {
  Column,
  ColumnPinningOptions,
  ColumnPinningPosition,
  ColumnPinningState,
  ColumnPinningTableState,
  makeStateUpdater,
  RowData,
  Table,
  TableFeature,
  Updater,
} from "@tanstack/react-table";

export const ColumnFreezingFeature: TableFeature = {
  getInitialState: (state): ColumnPinningTableState => {
    return {
      ...state,
      columnPinning: {
        left: state?.columnPinning?.left,
        right: state?.columnPinning?.right,
      }
    };
  },

  getDefaultOptions: <TData extends RowData>(
    table: Table<TData>
  ): ColumnPinningOptions => {
    return {
      enableColumnPinning: true,
      onColumnPinningChange: makeStateUpdater("columnPinning", table),
    } as ColumnPinningOptions;
  },

  createColumn: <TData extends RowData>(
    column: Column<TData>,
    table: Table<TData>
  ) => {
    column.getIsPinned = () => {
      const { left, right } = table.getState().columnPinning;
      const frozenLeft = left?.includes(column.id);
      const frozenRight = right?.includes(column.id);
      return (frozenLeft && "left") || (frozenRight && "right") || false;
    };

    column.getCanPin = () => {
      return table.options.enableColumnPinning ?? false;
    };

    column.pin = (position: ColumnPinningPosition) => {
      const safeUpdater: Updater<ColumnPinningState> = (prevState) => {
        const newState = { ...prevState } ?? {
          left: [],
          right: [],
        };

        if (prevState && prevState.left) {
          newState.left = [...prevState.left];
        }

        if (prevState && prevState.right) {
          newState.right = [...prevState.right];
        }

        if (position === false) {
          newState.left = newState.left?.filter((id) => id !== column.id);
          newState.right = newState.right?.filter((id) => id !== column.id);
        } else {
          newState[position]?.push(column.id);
        }

        return newState;
      };
      table.options.onColumnPinningChange?.(safeUpdater);
    };
  },
};
