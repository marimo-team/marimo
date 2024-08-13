/* Copyright 2024 Marimo. All rights reserved. */
import { CSSProperties } from "react";
import {
  TableFeature,
  RowData,
  makeStateUpdater,
  Table,
  Column,
  Updater,
} from "@tanstack/react-table";
import {
  ColumnPinningTableState,
  ColumnPinningOptions,
  ColumnPinningState,
  ColumnPinningPosition,
} from "./types";

export const ColumnPinningFeature: TableFeature = {
  // define the column pinning's initial state
  getInitialState: (state): ColumnPinningTableState => {
    return {
      // default to no pinning
      columnPinning: { left: [], right: [] },
      ...state,
    };
  },

  // define the column pinning's default options
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
    // get the column's pinning state
    column.getIsPinned = (): ColumnPinningPosition => {
      const pinningState = table.getState().columnPinning;
      return pinningState.left?.includes(column.id)
        ? "left"
        : pinningState.right?.includes(column.id)
          ? "right"
          : false;
    };

    // get if the column can be pinned
    column.getCanPin = (): boolean => {
      return table.options.enableColumnPinning ?? false;
    };

    // set the column's pinning state
    column.setColumnPinning = (position?: ColumnPinningPosition) => {
      const safeUpdater: Updater<ColumnPinningState> = (old) => {
        // get the previous pinning state
        const prevValue = old.left?.includes(column.id)
          ? "left"
          : old.right?.includes(column.id)
            ? "right"
            : false;

        // initialize the new pinning state
        let newState: ColumnPinningState = old;

        // If prevValue and position are equal, do nothing
        if (prevValue === position) {
          return newState;
        }

        // If prevValue is false and position is set,
        // add the column to the specified side
        if (prevValue === false && position) {
          newState = {
            ...old,
            [position]: [...(old[position] || []), column.id],
          };
        }

        // If prevValue isn't false and position is false,
        // remove the column from the specified side
        if (prevValue !== false && !position) {
          newState = {
            ...old,
            [prevValue]: old[prevValue]?.filter((id) => id !== column.id),
          };
        }

        // If prevValue isn't false and position is different,
        // move the column to the new side
        if (prevValue !== false && position && prevValue !== position) {
          newState = {
            ...old,
            [prevValue]: old[prevValue]?.filter((id) => id !== column.id),
            [position]: [...(old[position] || []), column.id],
          };
        }

        // If only "select" column is pinned to the left, unpin it
        if (
          position !== "left" &&
          newState.left?.length === 1 &&
          newState.left[0] === "select"
        ) {
          // unpin the 'select' column
          table.getColumn("select")?.pin(false);

          // remove the 'select' column from the left side
          newState = {
            ...newState,
            left: [],
          };
        }

        return newState;
      };
      table.options.onColumnPinningChange?.(safeUpdater);
    };

    // toggle the column's pinning state
    column.toggleColumnPinning = (position: ColumnPinningPosition) => {
      // get the column pinning state
      const { columnPinning } = table.getState();

      // if the column is being pinned to the left,
      // but the 'select' column is not pinned to the left,
      // pin the 'select' column to the left
      if (position === "left" && !columnPinning.left?.includes("select")) {
        // pin the 'select' column to the left
        const selectColumn = table.getColumn("select");
        if (selectColumn) {
          // always setColumnPinning first then pin
          selectColumn.setColumnPinning("left");
          selectColumn.pin("left");
        }
      }
      column.setColumnPinning(position);
      column.pin(position);
    };

    // get the column's common pinning styles
    column.getCommonPinningStyles = (): CSSProperties => {
      // get the column's pinning state
      const isPinned = column.getIsPinned();

      // get if the column is the last pinned column on the left
      const isLastLeftPinnedColumn =
        isPinned === "left" &&
        column.getIsLastColumn("left") &&
        // don't apply the box shadow to the 'select' column
        column.id !== "select";

      // get if the column is the first pinned column on the right
      const isFirstRightPinnedColumn =
        isPinned === "right" && column.getIsFirstColumn("right");

      return {
        // apply a box shadow to the column if
        // it is the last pinned column on the left
        // or the first pinned column on the right
        boxShadow: isLastLeftPinnedColumn
          ? "-4px 0 4px -4px gray inset"
          : isFirstRightPinnedColumn
            ? "4px 0 4px -4px gray inset"
            : undefined,

        // set the column's width
        width: column.getSize(),

        // set the column's left position
        left:
          isPinned === "left"
            ? `${
                column.getStart("left") -
                (column.id === "select" ? 0 : (column.getSize() * 4) / 5)
              }px`
            : undefined,

        // set the column's right position
        right:
          isPinned === "right" ? `${column.getAfter("right")}px` : undefined,

        // set the column's opacity, position, and z-index
        opacity: isPinned ? 0.95 : 1,
        position: isPinned ? "sticky" : "relative",
        zIndex: isPinned ? 1 : 0,
      };
    };
  },
};
