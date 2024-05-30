/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import type { CellId } from "./ids";
import { type NotebookState, notebookAtom } from "./cells";
import type { EditorView } from "@codemirror/view";
import type { CellConfig, CellStatus } from "./types";

/**
 * Holds state for the last focused cell.
 */
export const lastFocusedCellIdAtom = atom<CellId | null>(null);

export const lastFocusedCellAtom = atom<{
  name: string;
  config: CellConfig;
  cellId: CellId;
  status: CellStatus;
  getEditorView: () => EditorView | null;
  hasOutput: boolean;
} | null>((get) => {
  const cellId = get(lastFocusedCellIdAtom);
  if (!cellId) {
    return null;
  }

  return cellFocusDetails(cellId, get(notebookAtom));
});

export function cellFocusDetailsAtom(cellId: CellId) {
  return atom((get) => {
    return cellFocusDetails(cellId, get(notebookAtom));
  });
}

function cellFocusDetails(cellId: CellId, notebookState: NotebookState) {
  const { cellData, cellHandles, cellRuntime } = notebookState;
  const data = cellData[cellId];
  const runtime = cellRuntime[cellId];
  const handle = cellHandles[cellId].current;
  if (!data || !handle) {
    return null;
  }
  const getEditorView = () => handle.editorView;

  return {
    cellId,
    name: data.name,
    config: data.config,
    status: runtime ? runtime.status : "idle",
    getEditorView: getEditorView,
    hasOutput: runtime?.output != null,
  };
}
