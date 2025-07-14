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
import type { ColumnEdit, Edits, PositionalEdit, RowEdit } from "./types";

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

export function isPositionalEdit(
  edit: Edits["edits"][number],
): edit is PositionalEdit {
  return "rowIdx" in edit && "columnId" in edit && "value" in edit;
}

export function isRowEdit(edit: Edits["edits"][number]): edit is RowEdit {
  return "rowIdx" in edit && "type" in edit;
}

export function isColumnEdit(edit: Edits["edits"][number]): edit is ColumnEdit {
  return "columnIdx" in edit && "type" in edit;
}
