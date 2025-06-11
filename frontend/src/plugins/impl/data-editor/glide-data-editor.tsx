/* Copyright 2024 Marimo. All rights reserved. */

import { inferFieldTypes } from "@/components/data-table/columns";
import {
  toFieldTypes,
  type FieldTypesWithExternalType,
} from "@/components/data-table/types";
import type { DataType } from "@/core/kernel/messages";
import DataEditor, {
  type GridCell,
  type Item,
  GridCellKind,
  type EditableGridCell,
} from "@glideapps/glide-data-grid";
import { useCallback } from "react";

interface GlideDataEditorProps<T> {
  data: T[];
  fieldTypes?: FieldTypesWithExternalType | null;
  rows: number;
}

export const GlideDataEditor = <T,>({
  data,
  fieldTypes,
  rows,
}: GlideDataEditorProps<T>) => {
  const columnFields = toFieldTypes(fieldTypes ?? inferFieldTypes(data));
  const columns = Object.entries(columnFields).map(
    ([columnName, fieldType]) => ({
      title: columnName,
      width: 100,
      kind: getColumnKind(fieldType),
    }),
  );
  const indexes = Object.keys(columnFields);

  const getCellContent = useCallback(
    (cell: Item): GridCell => {
      const [col, row] = cell;
      const dataRow = data[row];

      const dataItem = String(dataRow[indexes[col] as keyof T]);

      return {
        kind: GridCellKind.Text,
        allowOverlay: true,
        readonly: false,
        displayData: dataItem,
        data: dataItem,
      };
    },
    [data, indexes],
  );

  const onCellEdited = useCallback(
    (cell: Item, newValue: EditableGridCell) => {
      if (newValue.kind !== GridCellKind.Text) {
        return;
      }

      const [col, row] = cell;
      const key = indexes[col];
      data[row][key as keyof T] = newValue.data as T[keyof T];
    },
    [data, indexes],
  );

  return (
    <DataEditor
      getCellContent={getCellContent}
      columns={columns}
      rows={rows}
      onCellEdited={onCellEdited}
      // editOnType={true}
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

export default GlideDataEditor;
