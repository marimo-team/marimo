/* Copyright 2024 Marimo. All rights reserved. */

import {
  type GridCell,
  GridCellKind,
  type GridSelection,
} from "@glideapps/glide-data-grid";
import { getTabSeparatedValues } from "@/components/data-table/range-focus/utils";
import type { DataType } from "@/core/kernel/messages";
import { copyToClipboard } from "@/utils/copy";
import { Logger } from "@/utils/Logger";

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

export async function pasteCells<T>(
  selection: GridSelection,
  data: T[],
  columnFields: Record<string, DataType>,
  indexes: string[],
  onAddEdits: (
    edits: Array<{
      rowIdx: number;
      columnId: string;
      value: unknown;
    }>,
  ) => void,
) {
  if (!selection.current) {
    return;
  }

  const { range } = selection.current;
  const { x: startCol, y: startRow } = range;

  try {
    let clipboardText = "";
    if (navigator.clipboard) {
      clipboardText = await navigator.clipboard.readText();
    } else {
      return;
    }
    // if (navigator.clipboard && window.isSecureContext) {
    //   clipboardText = await navigator.clipboard.readText();
    // } else {
    //   // Fallback for non-secure contexts
    //   const textArea = document.createElement("textarea");
    //   textArea.style.position = "fixed";
    //   textArea.style.left = "-999999px";
    //   textArea.style.top = "-999999px";
    //   document.body.append(textArea);
    //   textArea.focus();

    //   try {
    //     document.execCommand("paste");
    //     clipboardText = textArea.value;
    //   } catch (error) {
    //     Logger.error("Failed to read from clipboard:", error);
    //     return;
    //   } finally {
    //     textArea.remove();
    //   }
    // }

    // Parse clipboard text (tab-separated values)
    const rows = clipboardText.trim().split("\n");
    const cellsToPaste: string[][] = rows.map((row) =>
      row.split("\t").map((cell) => cell.trim()),
    );

    // Apply pasted data to the grid
    const edits: Array<{
      rowIdx: number;
      columnId: string;
      value: unknown;
    }> = [];

    for (const [rowIdx, rowData] of cellsToPaste.entries()) {
      const targetRow = startRow + rowIdx;
      if (targetRow >= data.length) {
        break; // Don't paste beyond the data bounds
      }

      for (const [colIdx, cellValue] of rowData.entries()) {
        const targetCol = startCol + colIdx;
        if (targetCol >= indexes.length) {
          break; // Don't paste beyond the column bounds
        }

        const columnId = indexes[targetCol];

        // Convert value based on column type
        const columnType = columnFields[columnId];
        let convertedValue: unknown = cellValue;

        switch (columnType) {
          case "number":
          case "integer": {
            const numValue = Number(cellValue);
            if (!Number.isNaN(numValue)) {
              convertedValue =
                columnType === "integer" ? Math.floor(numValue) : numValue;
            }
            break;
          }
          case "boolean":
            convertedValue =
              cellValue.toLowerCase() === "true" || cellValue === "1";
            break;
          default:
            convertedValue = cellValue;
        }

        edits.push({
          rowIdx: targetRow,
          columnId,
          value: convertedValue,
        });

        // Update data in place
        data[targetRow][targetCol] = convertedValue as T;
      }
    }

    // Apply all edits at once
    if (edits.length > 0) {
      onAddEdits(edits);
    }
  } catch (error) {
    Logger.error("Failed to paste cells:", error);
  }
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
