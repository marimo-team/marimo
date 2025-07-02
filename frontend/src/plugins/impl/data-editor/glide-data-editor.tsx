/* Copyright 2024 Marimo. All rights reserved. */

import DataEditor, {
  CompactSelection,
  type EditableGridCell,
  type GridCell,
  GridCellKind,
  type GridColumn,
  GridColumnIcon,
  type GridKeyEventArgs,
  type GridSelection,
  type Item,
} from "@glideapps/glide-data-grid";
import { useMemo, useState } from "react";
import useEvent from "react-use-event-hook";
import { inferFieldTypes } from "@/components/data-table/columns";
import {
  type FieldTypesWithExternalType,
  toFieldTypes,
} from "@/components/data-table/types";
import type { DataType } from "@/core/kernel/messages";
import { useTheme } from "@/theme/useTheme";
import { logNever } from "@/utils/assertNever";

// CSS is required for default editor styles
import "@glideapps/glide-data-grid/dist/index.css";
import { isCopyKey, isPasteKey } from "@/components/editor/controls/utils";
import { getGlideTheme } from "./themes";
import { copyCells, getColumnWidth, pasteCells } from "./utils";

interface GlideDataEditorProps<T> {
  data: T[];
  fieldTypes?: FieldTypesWithExternalType | null;
  rows: number;
  onAddEdits: (
    edits: Array<{
      rowIdx: number;
      columnId: string;
      value: unknown;
    }>,
  ) => void;
  host: HTMLElement;
}

export const GlideDataEditor = <T,>({
  data,
  fieldTypes,
  rows,
  onAddEdits,
  host,
}: GlideDataEditorProps<T>) => {
  const { theme } = useTheme();
  const [selection, setSelection] = useState<GridSelection>({
    columns: CompactSelection.empty(),
    rows: CompactSelection.empty(),
  });

  const columnFields = toFieldTypes(fieldTypes ?? inferFieldTypes(data));

  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({});

  const columns = useMemo(() => {
    return Object.entries(columnFields).map(([columnName, fieldType]) => ({
      title: columnName,
      width:
        columnWidths[columnName] ?? getColumnWidth(fieldType, data, columnName),
      kind: getColumnKind(fieldType),
      icon: getColumnHeaderIcon(fieldType),
    }));
  }, [columnFields, data, columnWidths]);

  const indexes = Object.keys(columnFields);

  const getCellContent = useEvent((cell: Item): GridCell => {
    const [col, row] = cell;
    const dataRow = data[row];

    const dataItem = dataRow[indexes[col] as keyof T];
    const columnKind = columns[col].kind;

    if (columnKind === GridCellKind.Boolean) {
      const value = Boolean(dataItem);
      return {
        kind: GridCellKind.Boolean,
        allowOverlay: false,
        readonly: false,
        data: value,
      };
    }

    if (columnKind === GridCellKind.Number && typeof dataItem === "number") {
      return {
        kind: GridCellKind.Number,
        allowOverlay: true,
        readonly: false,
        displayData: String(dataItem),
        data: dataItem,
      };
    }

    return {
      kind: GridCellKind.Text,
      allowOverlay: true,
      readonly: false,
      displayData: String(dataItem),
      data: String(dataItem),
    };
  });

  const onCellEdited = useEvent((cell: Item, newValue: EditableGridCell) => {
    const [col, row] = cell;
    const key = indexes[col];

    // Mutate the data in place is demonstrated in the docs
    // eslint-disable-next-line react-hooks/react-compiler
    data[row][key as keyof T] = newValue.data as T[keyof T];

    onAddEdits([
      {
        rowIdx: row,
        columnId: key,
        value: newValue.data,
      },
    ]);
  });

  const onColumnResize = useEvent((column: GridColumn, newSize: number) => {
    setColumnWidths((prev) => ({
      ...prev,
      [column.title]: newSize,
    }));
  });

  const validateCell = useEvent(
    (cell: Item, newValue: EditableGridCell, _prevValue: GridCell): boolean => {
      const [col, _row] = cell;
      const key = indexes[col];

      const columnType = columnFields[key];
      // Verify the new value is of the correct type
      switch (columnType) {
        case "number":
        case "integer":
          if (Number.isNaN(Number(newValue.data))) {
            return false;
          }
          break;
        case "boolean":
          if (typeof newValue.data !== "boolean") {
            return false;
          }
          break;
      }

      return true;
    },
  );

  const onKeyDown = useEvent((e: GridKeyEventArgs) => {
    if (isCopyKey(e as unknown as React.KeyboardEvent<HTMLElement>)) {
      copyCells(selection, getCellContent);
      return;
    }

    if (isPasteKey(e as unknown as React.KeyboardEvent<HTMLElement>)) {
      pasteCells(selection, data, columnFields, indexes, onAddEdits);
      return;
    }
  });

  const memoizedThemeValues = useMemo(() => getGlideTheme(theme), [theme]);
  const experimental = useMemo(
    () => ({
      eventTarget: (host.shadowRoot as unknown as HTMLElement) || window,
    }),
    [host],
  );

  return (
    <DataEditor
      getCellContent={getCellContent}
      columns={columns}
      rows={rows}
      smoothScrollX={true}
      smoothScrollY={true}
      validateCell={validateCell}
      // getCellsForSelection={true} // Enables copy, TODO: Not working, improve perf
      onPaste={true} // Enables paste, TODO: Not working, improve perf
      onKeyDown={onKeyDown}
      width="100%"
      onCellEdited={onCellEdited}
      gridSelection={selection}
      onGridSelectionChange={setSelection}
      onColumnResize={onColumnResize}
      theme={memoizedThemeValues}
      experimental={experimental}
    />
  );
};

function getColumnKind(fieldType: DataType): GridCellKind {
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

function getColumnHeaderIcon(fieldType: DataType): GridColumnIcon {
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

export default GlideDataEditor;
