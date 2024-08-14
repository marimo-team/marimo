/* Copyright 2024 Marimo. All rights reserved. */
import { atom, useAtomValue, useSetAtom } from "jotai";
import type { CellId } from "./ids";
import { type NotebookState, SCRATCH_CELL_ID, notebookAtom } from "./cells";
import type { EditorView } from "@codemirror/view";
import type { CellConfig, RuntimeState } from "../network/types";

/**
 * Holds state for the last focused cell.
 */
const lastFocusedCellIdAtom = atom<CellId | null>(null);

export function useLastFocusedCellId() {
  return useAtomValue(lastFocusedCellIdAtom);
}
export function useSetLastFocusedCellId() {
  const setter = useSetAtom(lastFocusedCellIdAtom);
  return (cellId: CellId | null) => {
    if (SCRATCH_CELL_ID === cellId) {
      return;
    }
    setter(cellId);
  };
}

export const lastFocusedCellAtom = atom<{
  name: string;
  config: CellConfig;
  cellId: CellId;
  status: RuntimeState;
  getEditorView: () => EditorView | null;
  hasOutput: boolean;
} | null>((get) => {
  const cellId = get(lastFocusedCellIdAtom);
  if (!cellId) {
    return null;
  }

  if (cellId === SCRATCH_CELL_ID) {
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
  const handle = cellHandles[cellId]?.current;
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
