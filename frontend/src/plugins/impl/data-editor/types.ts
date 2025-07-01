/* Copyright 2024 Marimo. All rights reserved. */

import type { FieldTypesWithExternalType } from "@/components/data-table/types";

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
