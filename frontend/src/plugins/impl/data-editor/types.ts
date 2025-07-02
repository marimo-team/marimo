/* Copyright 2024 Marimo. All rights reserved. */

import type { GridCellKind, GridColumn } from "@glideapps/glide-data-grid";
import type { FieldTypesWithExternalType } from "@/components/data-table/types";

export interface Edits {
  edits: Array<{
    rowIdx: number;
    columnId: string;
    value: unknown;
  }>;
}

export type GridColumnWithKind = GridColumn & {
  kind: GridCellKind;
};

export interface DataEditorProps<T> {
  data: T[];
  fieldTypes: FieldTypesWithExternalType | null | undefined;
  edits: Array<{
    rowIdx: number;
    columnId: string;
    value: unknown;
  }>;
  onAddEdits: (
    edits: Array<{
      rowIdx: number;
      columnId: string;
      value: unknown;
    }>,
  ) => void;
  onAddRows: (newRows: object[]) => void;
  columnSizingMode: "fit" | "auto";
}
