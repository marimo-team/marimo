/* Copyright 2026 Marimo. All rights reserved. */

import type { ColumnTypes, EditorRow } from "./types";

const TRUE_BOOLEAN_STRINGS = new Set(["true", "t", "yes", "y", "1"]);
const FALSE_BOOLEAN_STRINGS = new Set(["false", "f", "no", "n", "0", ""]);

export function normalizeBoolean(value: unknown, columnName: string): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return Boolean(value);
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (TRUE_BOOLEAN_STRINGS.has(normalized)) {
      return true;
    }
    if (FALSE_BOOLEAN_STRINGS.has(normalized)) {
      return false;
    }
  }
  throw new Error(
    `Invalid boolean value for column '${columnName}': ${String(value)}`,
  );
}

export function normalizeConfiguredColumns(
  data: EditorRow[],
  columnTypes: ColumnTypes,
): EditorRow[] {
  return data.map((row) => {
    const normalizedRow = { ...row };
    for (const [columnName, columnType] of columnTypes) {
      if (columnType === "boolean" && columnName in normalizedRow) {
        normalizedRow[columnName] = normalizeBoolean(
          normalizedRow[columnName],
          columnName,
        );
      }
    }
    return normalizedRow;
  });
}
