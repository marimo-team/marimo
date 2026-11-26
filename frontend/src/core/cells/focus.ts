/* Copyright 2026 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import { atom, useAtomValue, type Getter } from "jotai";
import { createReducerAndAtoms } from "@/utils/createReducer";
import {
  type CellRunStatus,
  cellExecutionInputsAtom,
  cellExecutionView,
  cellOutputAtom,
} from "@/core/executions";
import type { CellConfig } from "../network/types";
import { cellRuntimeAtom, notebookAtom } from "./cells";
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
  status: CellRunStatus;
  blocked: boolean;
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

  return cellFocusDetails(get, cellId);
});

export function cellFocusDetailsAtom(cellId: CellId) {
  return atom((get) => cellFocusDetails(get, cellId));
}

function cellFocusDetails(get: Getter, cellId: CellId) {
  const { cellData, cellHandles } = get(notebookAtom);
  const data = cellData[cellId];
  const handle = cellHandles[cellId]?.current;
  if (!data || !handle) {
    return null;
  }
  const getEditorView = () => handle.editorView;
  const execution = cellExecutionView(get(cellExecutionInputsAtom), cellId);

  return {
    cellId,
    name: data.name,
    config: data.config,
    status: execution.status,
    blocked: execution.blocked,
    getEditorView: getEditorView,
    hasOutput: get(cellOutputAtom(cellId)) !== null,
    hasConsoleOutput: get(cellRuntimeAtom(cellId)).consoleOutputs.length > 0,
  };
}

export { useCellFocusActions, cellFocusAtom };

export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
  cellFocusAtom,
};
