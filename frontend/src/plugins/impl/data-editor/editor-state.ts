/* Copyright 2026 Marimo. All rights reserved. */

import type { FieldTypes } from "@/components/data-table/types";
import {
  insertColumn,
  modifyColumnFields,
  removeColumn,
  renameColumn,
} from "./data-utils";
import { isColumnEdit, isPositionalEdit, isRowEdit } from "./glide-utils";
import { BulkEdit, type EditorState, type Edits } from "./types";

export function applyEditorEdits(
  state: EditorState,
  edits: Edits["edits"],
): EditorState {
  let nextData = [...state.data];
  let nextColumnFields: FieldTypes = new Map(state.columnFields);

  for (const edit of edits) {
    if (isPositionalEdit(edit)) {
      if (edit.rowIdx < 0) {
        continue;
      }
      while (nextData.length <= edit.rowIdx) {
        nextData.push({});
      }
      nextData[edit.rowIdx] = {
        ...nextData[edit.rowIdx],
        [edit.columnId]: edit.value,
      };
      if (!nextColumnFields.has(edit.columnId)) {
        nextColumnFields.set(edit.columnId, "unknown");
      }
      continue;
    }

    if (isRowEdit(edit)) {
      if (
        edit.type === BulkEdit.Remove &&
        edit.rowIdx >= 0 &&
        edit.rowIdx < nextData.length
      ) {
        nextData.splice(edit.rowIdx, 1);
      }
      continue;
    }

    if (!isColumnEdit(edit)) {
      continue;
    }

    const columnName = [...nextColumnFields.keys()][edit.columnIdx];
    switch (edit.type) {
      case BulkEdit.Remove:
        if (columnName === undefined) {
          break;
        }
        nextData = removeColumn(nextData, columnName);
        nextColumnFields = modifyColumnFields({
          columnFields: nextColumnFields,
          columnIdx: edit.columnIdx,
          type: "remove",
        });
        break;
      case BulkEdit.Insert:
        if (
          !edit.newName ||
          edit.columnIdx < 0 ||
          edit.columnIdx > nextColumnFields.size ||
          nextColumnFields.has(edit.newName)
        ) {
          break;
        }
        nextData = insertColumn(nextData, edit.newName, edit.columnIdx);
        nextColumnFields = modifyColumnFields({
          columnFields: nextColumnFields,
          columnIdx: edit.columnIdx,
          type: "insert",
          dataType: edit.dataType,
          newColumnName: edit.newName,
        });
        break;
      case BulkEdit.Rename:
        if (
          columnName === undefined ||
          !edit.newName ||
          nextColumnFields.has(edit.newName)
        ) {
          break;
        }
        nextData = renameColumn(nextData, columnName, edit.newName);
        nextColumnFields = modifyColumnFields({
          columnFields: nextColumnFields,
          columnIdx: edit.columnIdx,
          type: "rename",
          dataType: nextColumnFields.get(columnName),
          newColumnName: edit.newName,
        });
        break;
    }
  }

  return { data: nextData, columnFields: nextColumnFields };
}
