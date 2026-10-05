/* Copyright 2026 Marimo. All rights reserved. */

import {
  GridCellKind,
  GridColumnIcon,
  type GridSelection,
} from "@glideapps/glide-data-grid";
import type { DataType } from "@/core/kernel/messages";
import { logNever } from "@/utils/assertNever";
import { Logger } from "@/utils/Logger";
import type {
  ColumnEdit,
  EditorRow,
  Edits,
  ModifiedGridColumn,
  PositionalEdit,
  RemoveRowEdit,
} from "./types";

export function getColumnKind(fieldType: DataType): GridCellKind {
  switch (fieldType) {
    case "string":
      return GridCellKind.Text;
    case "number":
      return GridCellKind.Number;
    case "boolean":
      return GridCellKind.Boolean;
    case "integer":
    case "date":
    case "datetime":
    case "time":
    case "geometry":
    case "unknown":
      return GridCellKind.Text;
    default:
      logNever(fieldType);
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
    case "geometry":
    case "unknown":
      return GridColumnIcon.HeaderString;
    default:
      logNever(fieldType);
      return GridColumnIcon.HeaderString;
  }
}

export function isValidCellValue(
  dataType: DataType | undefined,
  value: unknown,
): boolean {
  switch (dataType) {
    case "number":
      return Number.isFinite(Number(value));
    case "integer":
      if (typeof value === "bigint") {
        return true;
      }
      if (typeof value === "number") {
        return Number.isFinite(value) && Number.isInteger(value);
      }
      if (typeof value === "string") {
        const normalized = value.trim();
        return /^[+-]?[0-9]+(?:\.0+)?$/u.test(normalized);
      }
      return false;
    case "boolean":
      return typeof value === "boolean";
    case undefined:
    case "string":
    case "date":
    case "datetime":
    case "time":
    case "geometry":
    case "unknown":
      return true;
    default:
      logNever(dataType);
      return false;
  }
}

export function isPositionalEdit(
  edit: Edits["edits"][number],
): edit is PositionalEdit {
  return "rowIdx" in edit && "columnId" in edit && "value" in edit;
}

export function isRowEdit(edit: Edits["edits"][number]): edit is RemoveRowEdit {
  return "rowIdx" in edit && "type" in edit;
}

export function isColumnEdit(edit: Edits["edits"][number]): edit is ColumnEdit {
  return "columnIdx" in edit && "type" in edit;
}

export function pasteCells(options: {
  selection: GridSelection;
  data: EditorRow[];
  columns: ModifiedGridColumn[];
  editableColumns: string[] | "all";
  onAddEdits: (edits: Edits["edits"]) => void;
}) {
  const { selection, data, onAddEdits, columns, editableColumns } = options;
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
          if (targetColIdx >= columns.length) {
            break;
          }

          const column = columns[targetColIdx];
          const columnType = column.dataType;
          const editable =
            editableColumns === "all" || editableColumns.includes(column.title);

          if (!editable) {
            continue;
          }

          // Convert the value based on the cell type
          let convertedValue: unknown = cellValue;

          switch (columnType) {
            case "integer": {
              const numValue = Number(cellValue);
              if (!isValidCellValue(columnType, cellValue)) {
                continue;
              }
              convertedValue = Number.isSafeInteger(numValue)
                ? numValue
                : cellValue.trim();
              break;
            }
            case "number": {
              const numValue = Number(cellValue);
              if (!isValidCellValue(columnType, numValue)) {
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
            case "string":
            case "date":
            case "datetime":
            case "time":
            case "geometry":
            case "unknown":
              break;
            default:
              logNever(columnType);
              continue;
          }

          // Get the column ID from the columns array using the title
          const columnId = columns[targetColIdx].title;

          edits.push({
            rowIdx: targetRowIdx,
            columnId,
            value: convertedValue,
          });
        }
      }

      if (edits.length > 0) {
        onAddEdits(edits);
      }
    })
    .catch((error) => {
      Logger.error("Failed to read clipboard data", error);
    });
}
