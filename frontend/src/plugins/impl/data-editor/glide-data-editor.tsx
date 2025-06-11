/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable ssr-friendly/no-dom-globals-in-module-scope */

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

const originalGetElementById = document.getElementById.bind(document);
document.getElementById = (id: string): HTMLElement | null => {
  const element = originalGetElementById.call(document, id);
  if (element) {
    return element;
  }

  // Check all marimo-data-editor shadow roots
  const editors = document.querySelectorAll("marimo-data-editor");
  for (const editor of editors) {
    const root = editor.shadowRoot;
    if (root) {
      const element = root.getElementById(id);
      if (element) {
        return element;
      }
    }
  }
  return null;
};

interface GlideDataEditorProps<T> {
  data: T[];
  fieldTypes?: FieldTypesWithExternalType | null;
  rows: number;
  host: HTMLElement;
}

export const GlideDataEditor = <T,>({
  data,
  fieldTypes,
  rows,
  host,
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
    <>
      <DataEditor
        getCellContent={getCellContent}
        columns={columns}
        rows={rows}
        width={300}
        height={300}
        onCellEdited={onCellEdited}
        experimental={{
          eventTarget: (host.shadowRoot as unknown as HTMLElement) || window,
        }}
        // editOnType={true}
      />
      <div
        id="portal"
        style={{ position: "fixed", left: 0, top: 0, zIndex: 9999 }}
      />
    </>
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
