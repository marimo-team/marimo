/* Copyright 2026 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import { atom, useAtomValue } from "jotai";
import { createReducerAndAtoms } from "@/utils/createReducer";
import type { CellConfig, RuntimeState } from "../network/types";
import { type NotebookState, notebookAtom } from "./cells";
import type { CellId } from "./ids";
import { SCRATCH_CELL_ID } from "./ids";
export interface CellFocusState {
  focusedCellId: CellId | null;
  lastFocusedCellId: CellId | null;
}

function initialState(): CellFocusState {
  return {
    focusedCellId: null,
    lastFocusedCellId: null,
  };
}

const {
  reducer,
  createActions,
  valueAtom: cellFocusAtom,
  useActions: useCellFocusActions,
} = createReducerAndAtoms(initialState, {
  // Focus a cell
  focusCell: (
    state: CellFocusState,
    payload: { cellId: CellId },
  ): CellFocusState => ({
    ...state,
    focusedCellId: payload.cellId,
    lastFocusedCellId: payload.cellId,
  }),
  // Toggle focus on a cell
  // If the cell is already focused, blur it
  // If the cell is not focused, focus it
  toggleCell: (
    state: CellFocusState,
    payload: { cellId: CellId },
  ): CellFocusState => {
    if (state.focusedCellId === payload.cellId) {
      return {
        ...state,
        focusedCellId: null,
      };
    }
    return {
      ...state,
      focusedCellId: payload.cellId,
      lastFocusedCellId: payload.cellId,
    };
  },
  // Blur the focused cell
  blurCell: (state: CellFocusState): CellFocusState => ({
    ...state,
    focusedCellId: null,
  }),
});

/**
 * Holds state for the last focused cell.
 */
export const lastFocusedCellIdAtom = atom(
  (get) => get(cellFocusAtom).lastFocusedCellId,
);

export function useLastFocusedCellId() {
  return useAtomValue(lastFocusedCellIdAtom);
}

export const lastFocusedCellAtom = atom<{
  name: string;
  config: CellConfig;
  cellId: CellId;
  status: RuntimeState;
  getEditorView: () => EditorView | null;
  hasOutput: boolean;
  hasConsoleOutput: boolean;
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
    hasConsoleOutput: runtime?.consoleOutputs != null,
  };
}

export { useCellFocusActions, cellFocusAtom };

export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
  cellFocusAtom,
};
