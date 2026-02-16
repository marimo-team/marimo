/* Copyright 2026 Marimo. All rights reserved. */

import type { Table } from "@tanstack/react-table";
import { SELECT_COLUMN_ID } from "../types";
import { stringifyUnknownValue } from "../utils";
import type { SelectedCell } from "./atoms";

/**
 * Get the values of the selected cells.
 */
export function getCellValues<TData>(
  table: Table<TData>,
  selectedCellIds: Set<string>,
): string {
  const rowValues = new Map<string, string[]>();

  for (const cellId of selectedCellIds) {
    if (cellId.includes(SELECT_COLUMN_ID)) {
      // Ignore select checkbox in tables
      continue;
    }

    const [rowId] = cellId.split("_"); // CellId is rowId_columnId
    const row = table.getRow(rowId);
    if (!row) {
      continue;
    }

    const tableCell = row.getAllCells().find((c) => c.id === cellId);
    if (!tableCell) {
      continue;
    }

    const values = rowValues.get(rowId) ?? [];
    values.push(stringifyUnknownValue({ value: tableCell.getValue() }));
    rowValues.set(rowId, values);
  }

  return getTabSeparatedValues([...rowValues.values()]);
}

export function getTabSeparatedValues(values: string[][]) {
  return values.map((row) => row.join("\t")).join("\n");
}

/**
 * Count selected cells excluding the select checkbox column.
 */
export function countDataCellsInSelection(
  selectedCellIds: Set<string>,
): number {
  let count = 0;
  for (const cellId of selectedCellIds) {
    if (!cellId.includes(SELECT_COLUMN_ID)) {
      count += 1;
    }
  }
  return count;
}

/**
 * Extract numeric values from the selected cells. Only finite numbers and
 * non-empty numeric strings (e.g. "42", "3.14", "0") are included. Skips select
 * checkbox column, missing cells, and all other types (boolean, null, etc.).
 */
export function getNumericValuesFromSelectedCells<TData>(
  table: Table<TData>,
  selectedCellIds: Set<string>,
): number[] {
  const numericValues: number[] = [];
  for (const cellId of selectedCellIds) {
    if (cellId.includes(SELECT_COLUMN_ID)) {
      continue;
    }
    const rowId = cellId.split("_")[0];
    const row = table.getRow(rowId);
    if (!row) {
      continue;
    }

    const tableCell = row.getAllCells().find((c) => c.id === cellId);
    if (!tableCell) {
      continue;
    }

    const value = tableCell.getValue();
    // Only accept numbers and strings
    // Skip booleans, null, etc.
    let num: number;
    if (typeof value === "number") {
      num = value;
    } else if (typeof value === "string") {
      if (value.trim() === "") {
        continue;
      }
      num = Number(value);
    } else {
      continue;
    }

    // Skip NaN and Infinity
    if (Number.isFinite(num)) {
      numericValues.push(num);
    }
  }
  return numericValues;
}

/**
 * Get the cell ids between two cells.
 */
export function getCellsBetween<TData>(
  table: Table<TData>,
  startCell: SelectedCell,
  endCell: SelectedCell,
): string[] {
  const startRow = table.getRow(startCell.rowId);
  const endRow = table.getRow(endCell.rowId);

  if (!startRow || !endRow) {
    return [];
  }

  const startRowIdx = startRow.index;
  const endRowIdx = endRow.index;
  const startColumnIdx = table.getColumn(startCell.columnId)?.getIndex();
  const endColumnIdx = table.getColumn(endCell.columnId)?.getIndex();

  if (startColumnIdx === undefined || endColumnIdx === undefined) {
    return [];
  }

  const minRow = Math.min(startRowIdx, endRowIdx);
  const maxRow = Math.max(startRowIdx, endRowIdx);
  const minCol = Math.min(startColumnIdx, endColumnIdx);
  const maxCol = Math.max(startColumnIdx, endColumnIdx);

  // Pre-allocate array with known size
  const result: string[] = [];
  const totalCells = (maxRow - minRow + 1) * (maxCol - minCol + 1);
  result.length = totalCells;
  let resultIndex = 0;

  const columnIds = table.getAllColumns().map((col) => col.id);
  const rows = table.getRowModel().rows;

  for (let i = minRow; i <= maxRow; i++) {
    const row = rows[i];
    const rowId = row.id;

    for (let j = minCol; j <= maxCol; j++) {
      const columnId = columnIds[j];
      result[resultIndex++] = getCellId(rowId, columnId);
    }
  }

  // Trim any unused slots
  result.length = resultIndex;
  return result;
}

/**
 * By default, the cell id is the row id and the column id separated by an underscore.
 * https://tanstack.com/table/latest/docs/guide/cells#cell-ids
 */
function getCellId(rowId: string, columnId: string) {
  return `${rowId}_${columnId}`;
}
