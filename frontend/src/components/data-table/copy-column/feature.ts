/* Copyright 2024 Marimo. All rights reserved. */
import type {
  Column,
  RowData,
  Table,
  TableFeature,
} from "@tanstack/react-table";
import type { CopyColumnOptions } from "./types";

export const CopyColumnFeature: TableFeature = {
  getDefaultOptions: <TData extends RowData>(
    table: Table<TData>,
  ): CopyColumnOptions => {
    return {
      enableCopyColumn: true,
    };
  },

  createColumn: <TData extends RowData>(
    column: Column<TData>,
    table: Table<TData>,
  ) => {
    column.getCanCopy = () => {
      return table.options.enableCopyColumn ?? false;
    };
  },
};
