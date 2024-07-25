/* Copyright 2024 Marimo. All rights reserved. */
import {
  TableFeature,
  RowData,
  makeStateUpdater,
  Table,
  Column,
  Updater,
} from "@tanstack/react-table";
import {
  ColumnFormattingTableState,
  ColumnFormattingOptions,
  ColumnFormattingState,
} from "./types";
import { DataType } from "@/core/kernel/messages";
import { type FormatOption } from "./types";
import { prettyNumber, prettyScientificNumber } from "@/utils/numbers";

export const ColumnFormattingFeature: TableFeature = {
  // define the column formatting's initial state
  getInitialState: (state): ColumnFormattingTableState => {
    return {
      columnFormatting: {},
      ...state,
    };
  },

  // define the new column formatting's default options
  getDefaultOptions: <TData extends RowData>(
    table: Table<TData>
  ): ColumnFormattingOptions => {
    return {
      enableColumnFormatting: true,
      onColumnFormattingChange: makeStateUpdater("columnFormatting", table),
    } as ColumnFormattingOptions;
  },

  createColumn: <TData extends RowData>(
    column: Column<TData>,
    table: Table<TData>
  ) => {
    column.getColumnFormatting = () => {
      return table.getState().columnFormatting[column.id];
    };

    column.getCanFormat = () => {
      return (
        (table.options.enableColumnFormatting &&
          column.columnDef.meta?.dataType !== "unknown" &&
          column.columnDef.meta?.dataType !== undefined) ??
        false
      );
    };

    column.setColumnFormatting = (value) => {
      const safeUpdater: Updater<ColumnFormattingState> = (old) => {
        return {
          ...old,
          [column.id]: value,
        };
      };
      table.options.onColumnFormattingChange?.(safeUpdater);
    };

    // apply column formatting
    column.applyColumnFormatting = (value) => {
      const dataType = column.columnDef.meta?.dataType;
      const format = column.getColumnFormatting?.();
      if (format) {
        return applyFormat(value, format, dataType);
      }
      return value;
    };
  },
};

// Apply formatting to a value given a format and data type
export const applyFormat = (
  value: unknown,
  format: FormatOption,
  dataType: DataType | undefined
) => {
  // If the value is null, return an empty string
  if (value === null || value === undefined || value === "") {
    return "";
  }
  // Handle date, number, string and boolean formatting
  switch (dataType) {
    case "date": {
      const date = new Date(value as string);
      switch (format) {
        case "Date":
          return date.toLocaleDateString("en-US");
        case "Datetime":
          return date.toISOString();
        case "Time":
          return date.toTimeString();
        default:
          return value;
      }
    }
    case "number": {
      const num = Number.parseFloat(value as string);
      switch (format) {
        case "Auto":
          return prettyNumber(num);
        case "Percent":
          return `${(num * 100).toFixed(2)}%`;
        case "Scientific":
          return prettyScientificNumber(num);
        case "Int":
          return num.toFixed(0);
        default:
          return value;
      }
    }
    case "string":
      switch (format) {
        case "Uppercase":
          return (value as string).toUpperCase();
        case "Lowercase":
          return (value as string).toLowerCase();
        case "Capitalize":
          return (
            (value as string).charAt(0).toUpperCase() +
            (value as string).slice(1)
          );
        case "Title":
          return (value as string)
            .split(" ")
            .map(
              (word) =>
                word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
            )
            .join(" ");
        default:
          return value;
      }
    case "boolean":
      switch (format) {
        case "Yes/No":
          return (value as boolean) ? "Yes" : "No";
        case "On/Off":
          return (value as boolean) ? "On" : "Off";
        default:
          return value;
      }
    default:
      return value;
  }
};
