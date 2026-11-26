/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { selectAtom } from "jotai/utils";
import { useMemo } from "react";
import { useDeleteCellCallback } from "@/components/editor/cell/useDeleteCell";
import type { CellId } from "@/core/cells/ids";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { writeCellCode } from "../codemirror/cell-documents";
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

export function useStagedAICell(cellId: CellId | undefined): Edit | undefined {
  const stagedCellAtom = useMemo(
    () =>
      selectAtom(
        stagedAICellsAtom,
        (cells) => (cellId === undefined ? undefined : cells.get(cellId)),
        Object.is,
      ),
    [cellId],
  );
  return useAtomValue(stagedCellAtom);
}

/** Keep or discard staged cells, whichever AI workflow staged them. */
export function useStagedCells() {
  const { removeStagedCell } = useStagedAICellsActions();
  const deleteCellCallback = useDeleteCellCallback();

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
        writeCellCode(cellId, edit.previousCode, { initialize: true });
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
