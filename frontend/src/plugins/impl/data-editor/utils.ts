/* Copyright 2024 Marimo. All rights reserved. */

import {
  type GridCell,
  GridCellKind,
  GridColumnIcon,
  type GridSelection,
} from "@glideapps/glide-data-grid";
import { getTabSeparatedValues } from "@/components/data-table/range-focus/utils";
import type { DataType } from "@/core/kernel/messages";
import { logNever } from "@/utils/assertNever";
import { copyToClipboard } from "@/utils/copy";
import { Logger } from "@/utils/Logger";
import type { Edits, ModifiedGridColumn } from "./types";

// Unused function, but keeping it temporarily if we switch to controlling selection state
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

export function pasteCells(options: {
  selection: GridSelection;
  data: unknown[];
  columns: ModifiedGridColumn[];
  onAddEdits?: (edits: Edits["edits"]) => void;
}) {
  const { selection, data, onAddEdits, columns } = options;
  if (!selection.current) {
    return;
  }

  const { range } = selection.current;
  const { x: startCol, y: startRow } = range;

  // Read clipboard data
  navigator.clipboard
    .readText()
    .then((clipboardText) => {
      if (!clipboardText.trim()) {
        return;
      }

      // Parse tab-separated values
      const rows = clipboardText.split("\n").filter((row) => row.trim());
      const parsedData: string[][] = [];

      for (const row of rows) {
        const cells = row.split("\t");
        parsedData.push(cells);
      }

      if (parsedData.length === 0) {
        return;
      }

      const edits: Edits["edits"] = [];

      for (const [rowIndex, dataRow] of parsedData.entries()) {
        if (!dataRow) {
          continue;
        }

        const targetRowIdx = startRow + rowIndex;

        // Check if we've exceeded the data bounds
        if (targetRowIdx >= data.length) {
          break;
        }

        for (const [colIndex, cellValue] of dataRow.entries()) {
          if (cellValue === undefined) {
            continue;
          }

          const targetColIdx = startCol + colIndex;

          // Check if we've exceeded the column bounds
          if (!columns || targetColIdx >= columns.length) {
            break;
          }

          const columnType = columns[targetColIdx].dataType;

          // Convert the value based on the cell type
          let convertedValue: unknown = cellValue;

          switch (columnType) {
            case "integer":
            case "number": {
              const numValue = Number(cellValue);
              if (Number.isNaN(numValue)) {
                continue;
              }
              convertedValue = numValue;
              break;
            }
            case "boolean": {
              const boolValue = cellValue.toLowerCase();
              convertedValue = boolValue === "true" || boolValue === "1";
              break;
            }
          }

          // Get the column ID from the columns array using the title
          const columnId = columns[targetColIdx].title;

          edits.push({
            rowIdx: targetRowIdx,
            columnId,
            value: convertedValue,
          });

          // eslint-disable-next-line react-hooks/react-compiler
          // @ts-expect-error - Update data in place
          data[targetRowIdx][columnId] = convertedValue;
        }
      }

      // Apply the edits if we have a callback
      if (onAddEdits && edits.length > 0) {
        onAddEdits(edits);
      }
    })
    .catch((error) => {
      Logger.error("Failed to read clipboard data", error);
    });
}

export function getColumnKind(fieldType: DataType): GridCellKind {
  switch (fieldType) {
    case "string":
      return GridCellKind.Text;
    case "number":
      return GridCellKind.Number;
    case "boolean":
      return GridCellKind.Boolean;
    default:
      return GridCellKind.Text;
  }
}

export function getColumnHeaderIcon(fieldType: DataType): GridColumnIcon {
  switch (fieldType) {
    case "string":
      return GridColumnIcon.HeaderString;
    case "number":
    case "integer":
      return GridColumnIcon.HeaderNumber;
    case "boolean":
      return GridColumnIcon.HeaderBoolean;
    case "date":
    case "datetime":
      return GridColumnIcon.HeaderDate;
    case "time":
      return GridColumnIcon.HeaderTime;
    case "unknown":
      return GridColumnIcon.HeaderString;
    default:
      logNever(fieldType);
      return GridColumnIcon.HeaderString;
  }
}
