/* Copyright 2026 Marimo. All rights reserved. */

import type { GridCellKind, GridColumn } from "@glideapps/glide-data-grid";
import type { FieldTypes } from "@/components/data-table/types";
import type { DataType } from "@/core/kernel/messages";

export type EditorRow = Record<string, unknown>;

// Shared transport for specialized column editors: dropdown columns use a
// string array, while checkbox columns use the boolean discriminator.
export type ColumnType = "boolean" | string[];
export type ColumnTypes = Map<string, ColumnType>;

export interface EditorState {
  data: EditorRow[];
  columnFields: FieldTypes;
  columnTypes: ColumnTypes;
}

export interface PositionalEdit {
  rowIdx: number;
  columnId: string;
  value: unknown;
}

export const BulkEdit = {
  Insert: "insert",
  Remove: "remove",
  Rename: "rename",
} as const;

export interface RemoveRowEdit {
  rowIdx: number;
  type: typeof BulkEdit.Remove;
}

export interface RemoveColumnEdit {
  columnIdx: number;
  type: typeof BulkEdit.Remove;
}

export interface RenameColumnEdit {
  columnIdx: number;
  newName: string;
  type: typeof BulkEdit.Rename;
}

export interface InsertColumnEdit {
  columnIdx: number;
  newName: string;
  type: typeof BulkEdit.Insert;
  dataType?: DataType;
}

export type ColumnEdit = RemoveColumnEdit | RenameColumnEdit | InsertColumnEdit;

export type Edit = PositionalEdit | RemoveRowEdit | ColumnEdit;

export interface Edits {
  edits: Edit[];
}

export type ModifiedGridColumn = GridColumn & {
  kind: GridCellKind;
  dataType: DataType;
  configuredType?: ColumnType;
};
