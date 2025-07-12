/* Copyright 2024 Marimo. All rights reserved. */

import type { FieldTypes } from "@/components/data-table/types";
import { Logger } from "@/utils/Logger";

/**
 * For modifying data, we do not worry about the order of the columns.
 * Because we define getCellContent based on columnTitle, the order does not matter.
 *
 * For column fields, we do care about the order
 */

export function removeColumn<T>(data: T[], columnIdx: number): T[] {
  return data.map((row) => {
    const rowData = row as Record<string, unknown>;
    const keys = Object.keys(rowData);

    // If the column index is out of bounds, return the original row
    if (columnIdx < 0 || columnIdx >= keys.length) {
      return rowData as T;
    }

    const keyToRemove = keys[columnIdx];

    // Create new object without the specified key
    const { [keyToRemove]: _, ...rest } = rowData;
    return rest as T;
  });
}

/**
 * Insert a new column at the end of the data.
 * @param data - The data to insert the column into
 * @param newName - The name of the new column
 * @returns The data with the new column inserted at the end
 */
export function insertColumn<T>(data: T[], newName?: string): T[] {
  if (!newName) {
    return data;
  }

  return data.map((row) => ({
    ...(row as Record<string, unknown>),
    [newName]: "",
  })) as T[];
}

export function renameColumn<T>(
  data: T[],
  oldName: string,
  newName: string,
): T[] {
  if (!oldName || !newName || oldName === newName) {
    return data;
  }

  return data.map((row) => {
    const rowData = row as Record<string, unknown>;
    const { [oldName]: _, ...rest } = rowData;
    return { ...rest, [newName]: rowData[oldName] } as T;
  });
}

// Order of columns is important
export function modifyColumnFields(
  columnFields: FieldTypes,
  columnIdx: number,
  type: "insert" | "remove" | "rename",
  newName?: string,
): FieldTypes {
  switch (type) {
    case "insert": {
      if (!newName) {
        Logger.error("newName is required for insert");
        return columnFields;
      }

      const entries = Object.entries(columnFields);
      const newEntries = [
        ...entries.slice(0, columnIdx),
        [newName, "string"], // Default to string type for new columns
        ...entries.slice(columnIdx),
      ];
      return Object.fromEntries(newEntries);
    }
    case "remove": {
      if (columnIdx < 0 || columnIdx >= Object.keys(columnFields).length) {
        return columnFields;
      }

      const entries = Object.entries(columnFields);
      const columnName = entries[columnIdx]?.[0];
      if (columnName) {
        const { [columnName]: _, ...rest } = columnFields;
        return rest;
      }
      return columnFields;
    }
    case "rename": {
      if (!newName) {
        Logger.error("newName is required for rename");
        return columnFields;
      }

      if (columnIdx < 0 || columnIdx >= Object.keys(columnFields).length) {
        return columnFields;
      }

      // Rename at the right index
      const entries = Object.entries(columnFields);
      const newEntries = [
        ...entries.slice(0, columnIdx),
        [newName, "string"],
        ...entries.slice(columnIdx + 1),
      ];
      return Object.fromEntries(newEntries);
    }
  }
}
