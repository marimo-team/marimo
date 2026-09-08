/* Copyright 2026 Marimo. All rights reserved. */

import type { FieldTypes } from "@/components/data-table/types";
import type { DataType } from "@/core/kernel/messages";
import { logNever } from "@/utils/assertNever";
import { Logger } from "@/utils/Logger";
import { BulkEdit, type EditorRow } from "./types";

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

export function removeColumn(
  data: EditorRow[],
  columnName: string,
): EditorRow[] {
  return data.map((row) => {
    const { [columnName]: _, ...rest } = row;
    return rest;
  });
}

export function insertColumn(
  data: EditorRow[],
  newName?: string,
  columnIdx?: number,
): EditorRow[] {
  if (!newName) {
    return data;
  }

  return data.map((row) => {
    const entries = Object.entries(row);
    const insertAt = Math.max(
      0,
      Math.min(columnIdx ?? entries.length, entries.length),
    );
    entries.splice(insertAt, 0, [newName, ""]);
    return Object.fromEntries(entries);
  });
}

export function renameColumn(
  data: EditorRow[],
  oldName: string,
  newName: string,
): EditorRow[] {
  if (!oldName || !newName || oldName === newName) {
    return data;
  }
  if (data.some((row) => Object.hasOwn(row, newName))) {
    return data;
  }

  return data.map((row) => {
    return Object.fromEntries(
      Object.entries(row).map(([columnName, value]) => [
        columnName === oldName ? newName : columnName,
        value,
      ]),
    );
  });
}

type ModifyColumnFieldsOptions = {
  columnFields: FieldTypes;
  columnIdx: number;
} & (
  | { type: typeof BulkEdit.Remove }
  | {
      type: typeof BulkEdit.Insert | typeof BulkEdit.Rename;
      newColumnName: string;
      dataType?: DataType;
    }
);

// Order of columns is important
export function modifyColumnFields(
  opts: ModifyColumnFieldsOptions,
): FieldTypes {
  const { columnFields, columnIdx } = opts;

  switch (opts.type) {
    case BulkEdit.Insert: {
      if (!opts.newColumnName) {
        Logger.error("newName is required for insert");
        return columnFields;
      }

      const entries = [...columnFields.entries()];
      const newEntries: Array<[string, DataType]> = [
        ...entries.slice(0, columnIdx),
        [opts.newColumnName, opts.dataType ?? "string"],
        ...entries.slice(columnIdx),
      ];
      return new Map(newEntries);
    }
    case BulkEdit.Remove: {
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
    case BulkEdit.Rename: {
      if (!opts.newColumnName) {
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
        [opts.newColumnName, opts.dataType ?? "string"],
        ...entries.slice(columnIdx + 1),
      ];
      return new Map(newEntries);
    }
    default:
      logNever(opts);
      return columnFields;
  }
}
