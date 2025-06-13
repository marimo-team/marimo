/* Copyright 2024 Marimo. All rights reserved. */

import type { Row, Table } from "@tanstack/react-table";
import { renderUnknownValue } from "../renderers";
import type { SelectedCell } from "./cell-selection-atoms";

/* Copyright 2024 Marimo. All rights reserved. */
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

// Returns the cell ids between two cells.
export function getCellsBetween<TData>(
  table: Table<TData>,
  rows: Array<Row<TData>>,
  cellStart: SelectedCell,
  cellEnd: SelectedCell,
): string[] {
  const startRow = table.getRow(cellStart.rowId);
  const endRow = table.getRow(cellEnd.rowId);

  if (!startRow || !endRow) {
    return [];
  }

  const startCell = startRow
    .getAllCells()
    .find((c) => c.id === cellStart.cellId);
  const endCell = endRow.getAllCells().find((c) => c.id === cellEnd.cellId);

  if (!startCell || !endCell) {
    return [];
  }

  const startRowIdx = startRow.index;
  const endRowIdx = endRow.index;
  const startColumnIdx = startCell.column.getIndex();
  const endColumnIdx = endCell.column.getIndex();

  const minRow = Math.min(startRowIdx, endRowIdx);
  const maxRow = Math.max(startRowIdx, endRowIdx);
  const minCol = Math.min(startColumnIdx, endColumnIdx);
  const maxCol = Math.max(startColumnIdx, endColumnIdx);

  // Pre-allocate array with known size
  const result: string[] = [];
  const totalCells = (maxRow - minRow + 1) * (maxCol - minCol + 1);
  result.length = totalCells;
  let resultIndex = 0;

  for (let i = minRow; i <= maxRow; i++) {
    const row = rows[i];
    const cells = row.getAllCells();

    for (let j = minCol; j <= maxCol; j++) {
      const cell = cells[j];
      result[resultIndex++] = cell.id;
    }
  }

  // Trim any unused slots
  result.length = resultIndex;
  return result;
}
