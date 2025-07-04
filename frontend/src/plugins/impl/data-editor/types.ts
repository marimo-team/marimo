/* Copyright 2024 Marimo. All rights reserved. */

import type { GridCellKind, GridColumn } from "@glideapps/glide-data-grid";
import type { FieldTypesWithExternalType } from "@/components/data-table/types";
import type { DataType } from "@/core/kernel/messages";

export interface Edits {
  edits: Array<{
    rowIdx: number;
    columnId: string;
    value: unknown;
  }>;
}

export type ModifiedGridColumn = GridColumn & {
  kind: GridCellKind;
  dataType: DataType;
};

export interface DataEditorProps<T> {
  data: T[];
  fieldTypes: FieldTypesWithExternalType | null | undefined;
  onAddEdits: (edits: Edits["edits"]) => void;
  onAddRows: (newRows: object[]) => void;
  columnSizingMode: "fit" | "auto";
}
