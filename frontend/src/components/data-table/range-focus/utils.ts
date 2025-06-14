/* Copyright 2024 Marimo. All rights reserved. */

import type { Table } from "@tanstack/react-table";
import { renderUnknownValue } from "../renderers";
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
    const [rowId] = cellId.split("_"); // CellId is rowId_columnId
    const row = table.getRow(rowId);
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
  cellStart: SelectedCell,
  cellEnd: SelectedCell,
): string[] {
  const startRow = table.getRow(cellStart.rowId);
  const endRow = table.getRow(cellEnd.rowId);

  const startRowIdx = startRow.index;
  const endRowIdx = endRow.index;
  const startColumnIdx = table.getColumn(cellStart.columnId)?.getIndex();
  const endColumnIdx = table.getColumn(cellEnd.columnId)?.getIndex();

  if (!startColumnIdx || !endColumnIdx) {
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
