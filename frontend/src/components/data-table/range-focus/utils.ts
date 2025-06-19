/* Copyright 2024 Marimo. All rights reserved. */

import type { Table } from "@tanstack/react-table";
import { renderUnknownValue } from "../renderers";
import { SELECT_COLUMN_ID } from "../types";
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
    values.push(renderUnknownValue({ value: tableCell.getValue() }));
    rowValues.set(rowId, values);
  }

  return [...rowValues.values()].map((values) => values.join("\t")).join("\n");
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
