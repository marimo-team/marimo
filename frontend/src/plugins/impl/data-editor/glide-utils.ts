/* Copyright 2024 Marimo. All rights reserved. */

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
  Edits,
  ModifiedGridColumn,
  PositionalEdit,
  RowEdit,
} from "./types";

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

export function pasteCells<T>(options: {
  selection: GridSelection;
  data: T[];
  setData: (updater: (prev: T[]) => T[]) => void;
  columns: ModifiedGridColumn[];
  onAddEdits: (edits: Edits["edits"]) => void;
}) {
  const { selection, data, setData, onAddEdits, columns } = options;
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
        }
      }

      if (edits.length > 0) {
        onAddEdits(edits);

        setData((prev: T[]) => {
          const newData = [...prev];

          // Apply all edits to the data
          for (const edit of edits) {
            if (isPositionalEdit(edit)) {
              const rowIdx = edit.rowIdx;
              const columnId = edit.columnId;

              if (rowIdx < newData.length) {
                const row = newData[rowIdx] as Record<string, unknown>;
                if (columnId in row) {
                  row[columnId] = edit.value;
                }
              }
            }
          }

          return newData;
        });
      }
    })
    .catch((error) => {
      Logger.error("Failed to read clipboard data", error);
    });
}
