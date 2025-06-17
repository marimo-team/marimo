/* Copyright 2024 Marimo. All rights reserved. */

import { Spreadsheet, Worksheet } from "@jspreadsheet-ce/react";
import type { CellChange, Column } from "jspreadsheet-ce";
import { Suspense, useCallback, useEffect, useRef } from "react";
import { inferFieldTypes } from "@/components/data-table/columns";
import {
  type FieldTypesWithExternalType,
  toFieldTypes,
} from "@/components/data-table/types";
import type { DataType } from "@/core/kernel/messages";
import { useTheme } from "@/theme/useTheme";
import { logNever } from "@/utils/assertNever";
import { cn } from "@/utils/cn";
import type { Edits } from "./types";

interface SpreadsheetEditorProps<T> {
  data: T[];
  onAddEdits: (edits: Edits) => void;
  fieldTypes?: FieldTypesWithExternalType | null;
  pagination: boolean;
  pageSize: number;
  host: HTMLElement;
}

const SpreadsheetEditor = <T,>({
  data,
  onAddEdits,
  fieldTypes,
  host,
  pagination,
  pageSize,
}: SpreadsheetEditorProps<T>) => {
  const spreadsheet = useRef<Spreadsheet>(null);
  const container = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  // By default, the spreadsheet does not blur when clicking outside of it.
  // This is a workaround to blur the spreadsheet
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (spreadsheet.current && container.current) {
        const path = e.composedPath();
        const clickedElement = path[0] as Node;
        if (!container.current.contains(clickedElement)) {
          const activeEditor = spreadsheet.current[0];
          if (activeEditor) {
            activeEditor.resetSelection();
          }
        }
      }
    };

    document.addEventListener("click", handleClickOutside);
    return () => {
      document.removeEventListener("click", handleClickOutside);
    };
  }, []);

  const columnFields = toFieldTypes(fieldTypes ?? inferFieldTypes(data));
  const columns: Column[] = Object.entries(columnFields).map(
    ([key, value]) => ({
      title: key,
      type: getColumnType(value),
    }),
  );

  const afterchanges = useCallback(
    (instance: Worksheet, cellChanges: CellChange[]) => {
      const newEdits: Edits = [];

      for (const cellChange of cellChanges) {
        const colIndex = Number.parseInt(cellChange.x);
        const rowIndex = Number.parseInt(cellChange.y);
        const columnName = columns[colIndex]?.title;

        // Cell changes' newValue is not correct at the moment. We can try to find the correct value from x and y
        // https://github.com/jspreadsheet/ce/issues/1764
        const newValue = instance.getValueFromCoords(colIndex, rowIndex);

        if (columnName) {
          newEdits.push({
            rowIdx: rowIndex,
            columnId: columnName,
            value: newValue,
          });
        }
      }

      onAddEdits(newEdits);
    },
    [columns, onAddEdits],
  );

  const dimensions = [columns.length, data.length]; // [cols, rows]
  const totalRows = data.length;
  const needsPagination = pagination && totalRows > pageSize;

  return (
    <div
      ref={container}
      className={cn("jss-theme-marimo", theme === "dark" && "dark")}
    >
      <Suspense fallback={<div>Loading...</div>}>
        <Spreadsheet
          ref={spreadsheet}
          tabs={false}
          toolbar={true}
          root={host.shadowRoot}
          data={data}
          onafterchanges={afterchanges}
        >
          <Worksheet
            columns={columns}
            data={data}
            minDimensions={dimensions}
            search={false}
            pagination={needsPagination ? pageSize : false}
          />
        </Spreadsheet>
      </Suspense>
    </div>
  );
};

type JSpreadsheetColumnType =
  | "text"
  | "numeric"
  | "hidden"
  | "dropdown"
  | "autocomplete"
  | "checkbox"
  | "radio"
  | "calendar"
  | "image"
  | "color"
  | "html";

function getColumnType(fieldType: DataType): JSpreadsheetColumnType {
  switch (fieldType) {
    case "string":
      return "text";
    case "number":
    case "integer":
      return "numeric";
    case "boolean":
      return "checkbox";
    case "date":
      return "calendar";
    case "datetime":
    case "time":
      return "text";
    case "unknown":
      return "text";
    default:
      logNever(fieldType);
      return "text";
  }
}

export default SpreadsheetEditor;
