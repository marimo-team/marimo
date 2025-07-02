/* Copyright 2024 Marimo. All rights reserved. */

import {
  type GridCell,
  GridCellKind,
  type GridSelection,
} from "@glideapps/glide-data-grid";
import { getTabSeparatedValues } from "@/components/data-table/range-focus/utils";
import type { DataType } from "@/core/kernel/messages";
import { copyToClipboard } from "@/utils/copy";

export function copyCells(
  selection: GridSelection,
  getCellContent: (cell: [number, number]) => GridCell,
) {
  if (!selection.current) {
    return;
  }

  const { range } = selection.current;
  const { x: startCol, y: startRow, width: numCols, height: numRows } = range;

  const cellsToCopy: string[][] = [];

  // Extract cell data from the selected range
  for (let row = startRow; row < startRow + numRows; row++) {
    const rowData: string[] = [];
    for (let col = startCol; col < startCol + numCols; col++) {
      const cell = getCellContent([col, row]);
      let cellValue = "";

      switch (cell.kind) {
        case GridCellKind.Text:
        case GridCellKind.Number:
          cellValue = cell.displayData || String(cell.data || "");
          break;
        case GridCellKind.Boolean:
          cellValue = cell.data ? "true" : "false";
          break;
        default:
          cellValue = "data" in cell ? String(cell.data || "") : "";
      }

      rowData.push(cellValue);
    }
    cellsToCopy.push(rowData);
  }

  const text = getTabSeparatedValues(cellsToCopy);
  copyToClipboard(text);
}

const MIN_WIDTHS: Record<DataType, number> = {
  boolean: 40,
  string: 80,
  number: 70,
  integer: 70,
  date: 100,
  datetime: 140,
  time: 80,
  unknown: 80,
};

const ICON_OFFSET_LENGTH = 30;
export function getColumnWidth<T>(
  fieldType: DataType,
  values: T[],
  columnTitle: string,
): number {
  if (fieldType === "boolean") {
    return 200;
  }

  const minWidth = MIN_WIDTHS[fieldType];

  const lengths = [
    columnTitle.length,
    ...values.map((value) => String(value).length),
  ];

  // 8px per character
  const calculatedWidth = Math.max(...lengths) * 8 + ICON_OFFSET_LENGTH;

  // Return the larger of minimum width or calculated width, capped at 600px
  return Math.min(Math.max(calculatedWidth, minWidth), 600);
}
