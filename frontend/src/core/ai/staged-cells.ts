/* Copyright 2026 Marimo. All rights reserved. */

import { useDeleteCellCallback } from "@/components/editor/cell/useDeleteCell";
import type { CellId } from "@/core/cells/ids";
import { createKeyedSelectorHook } from "@/core/state/create-keyed-selector-hook";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { getCellEditorView } from "../cells/cells";
import { useCellActions } from "../cells/actions";
import { prepareCellCodeUpdate } from "../codemirror/language/cell-code";
import type { EditType } from "./tools/edit-notebook-tool";

/** Pending AI edits shared by chat and agent workflows. */

export type Edit =
  | { type: Extract<EditType, "update_cell">; previousCode: string }
  | { type: Extract<EditType, "add_cell"> }
  | { type: Extract<EditType, "delete_cell">; previousCode: string };

export type StagedAICells = Map<CellId, Edit>;

const initialState = (): StagedAICells => {
  return new Map();
};

const {
  valueAtom: stagedAICellsAtom,
  useActions: useStagedAICellsActions,
  createActions,
  reducer,
} = createReducerAndAtoms(initialState, {
  addStagedCell: (state, action: { cellId: CellId; edit: Edit }) => {
    const { cellId, edit } = action;
    return new Map([...state, [cellId, edit]]);
  },
  reconcileStagedCells: (state, cellIds: readonly string[]) => {
    const existing = new Set(cellIds);
    const removed = [...state.keys()].filter((id) => !existing.has(id));
    if (removed.length === 0) {
      return state;
    }
    const next = new Map(state);
    for (const id of removed) {
      next.delete(id);
    }
    return next;
  },
  removeStagedCell: (state, cellId: CellId) => {
    if (!state.has(cellId)) {
      return state;
    }
    const newState = new Map(state);
    newState.delete(cellId);
    return newState;
  },
});

export { useStagedAICellsActions };

export const useStagedAICell = createKeyedSelectorHook(
  stagedAICellsAtom,
  (cells, cellId: CellId | undefined) =>
    cellId === undefined ? undefined : cells.get(cellId),
);

/** Keep or discard staged cells, whichever AI workflow staged them. */
export function useStagedCells() {
  const { removeStagedCell } = useStagedAICellsActions();
  const { setCellCode } = useCellActions();
  const deleteCellCallback = useDeleteCellCallback();

  // Only a mounted editor infers the cell's language; otherwise use the document.
  const writeCellCode = (cellId: CellId, code: string) => {
    const editorView = getCellEditorView(cellId);
    if (editorView) {
      const update = prepareCellCodeUpdate(editorView.state, code, {
        initialize: true,
      });
      if (update) {
        editorView.dispatch(update);
      }
    } else {
      setCellCode({ cellId, code });
    }
  };

  const deleteStagedCell = (cellId: CellId) => {
    removeStagedCell(cellId);
    deleteCellCallback({ cellId });
  };

  const acceptStagedCell = (cellId: CellId, edit: Edit) => {
    if (edit.type === "delete_cell") {
      deleteStagedCell(cellId);
    } else {
      removeStagedCell(cellId);
    }
  };

  const rejectStagedCell = (cellId: CellId, edit: Edit) => {
    switch (edit.type) {
      case "update_cell":
        writeCellCode(cellId, edit.previousCode);
        removeStagedCell(cellId);
        break;
      case "add_cell":
        deleteStagedCell(cellId);
        break;
      case "delete_cell":
        removeStagedCell(cellId);
        break;
    }
  };

  return { acceptStagedCell, rejectStagedCell };
}

export { stagedAICellsAtom };
export const visibleForTesting = {
  createActions,
  reducer,
  initialState,
};
