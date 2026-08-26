/* Copyright 2026 Marimo. All rights reserved. */

import type { FieldTypes } from "@/components/data-table/types";
import type { DataType } from "@/core/kernel/messages";
import { Logger } from "@/utils/Logger";

export function orderColumnFields(
  columnFields: FieldTypes,
  columnNames: string[],
): FieldTypes {
  const ordered = new Map<string, DataType>();
  for (const columnName of columnNames) {
    ordered.set(columnName, columnFields.get(columnName) ?? "unknown");
  }
  for (const [columnName, dataType] of columnFields) {
    if (!ordered.has(columnName)) {
      ordered.set(columnName, dataType);
    }
  }
  return ordered;
}

export function removeColumn<T>(data: T[], columnName: string): T[] {
  return data.map((row) => {
    const rowData = row as Record<string, unknown>;
    const { [columnName]: _, ...rest } = rowData;
    return rest as T;
  });
}

export function insertColumn<T>(
  data: T[],
  newName?: string,
  columnIdx?: number,
): T[] {
  if (!newName) {
    return data;
  }

  return data.map((row) => {
    const entries = Object.entries(row as Record<string, unknown>);
    const insertAt = Math.max(
      0,
      Math.min(columnIdx ?? entries.length, entries.length),
    );
    entries.splice(insertAt, 0, [newName, ""]);
    return Object.fromEntries(entries) as T;
  });
}

export function renameColumn<T>(
  data: T[],
  oldName: string,
  newName: string,
): T[] {
  if (!oldName || !newName || oldName === newName) {
    return data;
  }
  if (
    data.some((row) => Object.hasOwn(row as Record<string, unknown>, newName))
  ) {
    return data;
  }

  return data.map((row) => {
    const rowData = row as Record<string, unknown>;
    return Object.fromEntries(
      Object.entries(rowData).map(([columnName, value]) => [
        columnName === oldName ? newName : columnName,
        value,
      ]),
    ) as T;
  });
}

// Order of columns is important
export function modifyColumnFields(opts: {
  columnFields: FieldTypes;
  columnIdx: number;
  type: "insert" | "remove" | "rename";
  dataType?: DataType;
  newColumnName?: string;
}): FieldTypes {
  const { columnFields, columnIdx, type, dataType, newColumnName } = opts;

  switch (type) {
    case "insert": {
      if (!newColumnName) {
        Logger.error("newName is required for insert");
        return columnFields;
      }

      const entries = [...columnFields.entries()];
      const newEntries: Array<[string, DataType]> = [
        ...entries.slice(0, columnIdx),
        [newColumnName, dataType || "string"],
        ...entries.slice(columnIdx),
      ];
      return new Map(newEntries);
    }
    case "remove": {
      if (columnIdx < 0 || columnIdx >= columnFields.size) {
        return columnFields;
      }

      const entries = [...columnFields.entries()];
      const columnName = entries[columnIdx]?.[0];
      if (columnName) {
        const next = new Map(columnFields);
        next.delete(columnName);
        return next;
      }
      return columnFields;
    }
    case "rename": {
      if (!newColumnName) {
        Logger.error("newName is required for rename");
        return columnFields;
      }

      if (columnIdx < 0 || columnIdx >= columnFields.size) {
        return columnFields;
      }

      // Rename at the right index
      const entries = [...columnFields.entries()];
      const newEntries: Array<[string, DataType]> = [
        ...entries.slice(0, columnIdx),
        [newColumnName, dataType || "string"],
        ...entries.slice(columnIdx + 1),
      ];
      return new Map(newEntries);
    }
  }
}
