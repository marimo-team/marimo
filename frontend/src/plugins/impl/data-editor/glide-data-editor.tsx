/* Copyright 2024 Marimo. All rights reserved. */

import DataEditor, {
  CompactSelection,
  type EditableGridCell,
  type GridCell,
  GridCellKind,
  type GridColumn,
  GridColumnIcon,
  type GridSelection,
  type Item,
  type Theme,
} from "@glideapps/glide-data-grid";
import { useMemo, useState } from "react";
import useEvent from "react-use-event-hook";
import { inferFieldTypes } from "@/components/data-table/columns";
import {
  type FieldTypesWithExternalType,
  toFieldTypes,
} from "@/components/data-table/types";
import type { DataType } from "@/core/kernel/messages";
import { type ResolvedTheme, useTheme } from "@/theme/useTheme";
import { logNever } from "@/utils/assertNever";

// CSS is required for default editor styles
import "@glideapps/glide-data-grid/dist/index.css";
import "./grid.css";

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

    const columnType = columnFields[key];
    // Verify the new value is of the correct type
    switch (columnType) {
      case "number":
      case "integer":
        if (Number.isNaN(Number(newValue.data))) {
          return;
        }
        break;
      case "boolean":
        if (typeof newValue.data !== "boolean") {
          return;
        }
        break;
    }

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
      getCellsForSelection={true}
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
function getColumnWidth<T>(
  fieldType: DataType,
  values: T[],
  columnTitle: string,
): number {
  if (fieldType === "boolean") {
    // Base it off title length
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

function getGlideTheme(theme: ResolvedTheme): Partial<Theme> | undefined {
  if (theme === "light") {
    return {
      lineHeight: 1.25,
    };
  }

  return {
    lineHeight: 1.25,
    accentColor: "#7c3aed",
    accentLight: "rgba(124, 58, 237, 0.15)",

    textDark: "#f4f4f5",
    textMedium: "#a1a1aa",
    textLight: "#71717a",
    textBubble: "#f4f4f5",

    bgIconHeader: "#a1a1aa",
    fgIconHeader: "#18181b",
    textHeader: "#d4d4d8",
    textHeaderSelected: "#18181b",

    bgCell: "#18181b",
    bgCellMedium: "#27272a",
    bgHeader: "#27272a",
    bgHeaderHasFocus: "#3f3f46",
    bgHeaderHovered: "#3f3f46",

    bgBubble: "#27272a",
    bgBubbleSelected: "#7c3aed",

    bgSearchResult: "#312e81",

    borderColor: "#27272a",
    drilldownBorder: "#7c3aed",

    linkColor: "#818cf8",

    headerFontStyle: "bold 14px",
    baseFontStyle: "13px",
  };
}
