/* Copyright 2024 Marimo. All rights reserved. */

import {
  makeStateUpdater,
  type Row,
  type RowData,
  type Table,
  type TableFeature,
} from "@tanstack/react-table";
import type { FocusRowOptions, FocusRowTableState } from "./types";

export const FocusRowFeature: TableFeature = {
  getInitialState: (state): FocusRowTableState => {
    return {
      ...state,
      focusedRowIdx: -1,
    };
  },

  getDefaultOptions: <TData extends RowData>(
    table: Table<TData>,
  ): FocusRowOptions => {
    return {
      enableFocusRow: true,
      onFocusRowChange: makeStateUpdater("focusedRowIdx", table),
    };
  },

  createRow: <TData extends RowData>(
    row: Row<TData>,
    table: Table<TData>,
  ): void => {
    row.focusRow = (updater) => {
      table.options.onFocusRowChange?.(updater);
    };

    row.getFocusedRowIdx = () => {
      return table.getState().focusedRowIdx;
    };
  },
};
