/* Copyright 2024 Marimo. All rights reserved. */
import type { CellId } from "./ids";
import { arrayShallowEquals } from "@/utils/arrays";
import { Objects } from "@/utils/objects";
import type { EditorView } from "@codemirror/view";
import type { LayoutState } from "../layout/layout";
import { isEqual } from "lodash-es";
import {
  type NotebookState,
  type LastSavedNotebook,
  staleCellIds,
} from "./cells";

export function notebookIsRunning(state: NotebookState) {
  return Object.values(state.cellRuntime).some(
    (cell) => cell.status === "running",
  );
}

export function notebookNeedsSave(
  state: NotebookState,
  layout: LayoutState,
  lastSavedNotebook: LastSavedNotebook | undefined,
) {
  if (!lastSavedNotebook) {
    return false;
  }
  const { cellIds, cellData } = state;
  const data = cellIds.inOrderIds.map((cellId) => cellData[cellId]);
  const codes = data.map((d) => d.code);
  const configs = data.map((d) => d.config);
  const names = data.map((d) => d.name);
  return (
    !arrayShallowEquals(codes, lastSavedNotebook.codes) ||
    !arrayShallowEquals(configs, lastSavedNotebook.configs) ||
    !arrayShallowEquals(names, lastSavedNotebook.names) ||
    !isEqual(layout.selectedLayout, lastSavedNotebook.layout.selectedLayout) ||
    !isEqual(layout.layoutData, lastSavedNotebook.layout.layoutData)
  );
}

export function notebookNeedsRun(state: NotebookState) {
  return staleCellIds(state).length > 0;
}

export function notebookCells(state: NotebookState) {
  return state.cellIds.inOrderIds.map((cellId) => state.cellData[cellId]);
}

export function notebookCellEditorViews({ cellHandles }: NotebookState) {
  const views: Record<CellId, EditorView> = {};
  for (const [cell, ref] of Objects.entries(cellHandles)) {
    if (!ref.current) {
      continue;
    }
    views[cell] = ref.current.editorView;
  }
  return views;
}

export function disabledCellIds(state: NotebookState) {
  const { cellIds, cellData } = state;
  return cellIds.inOrderIds
    .map((cellId) => cellData[cellId])
    .filter((cell) => cell.config.disabled);
}

export function enabledCellIds(state: NotebookState) {
  const { cellIds, cellData } = state;
  return cellIds.inOrderIds
    .map((cellId) => cellData[cellId])
    .filter((cell) => !cell.config.disabled);
}

export function canUndoDeletes(state: NotebookState) {
  return state.history.length > 0;
}
