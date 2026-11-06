/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { selectAtom } from "jotai/utils";
import { useMemo } from "react";
import { useDeleteCellCallback } from "@/components/editor/cell/useDeleteCell";
import { CellId } from "@/core/cells/ids";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { Logger } from "@/utils/Logger";
import { getCellEditorView } from "../cells/cells";
import { useCellActions } from "../cells/actions";
import { prepareCellCodeUpdate } from "../codemirror/language/cell-code";
import type { JotaiStore } from "../state/jotai";
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

interface UpdateStagedCellAction {
  cellId: CellId;
  code: string;
}

/** Manage staged cells without assuming which AI workflow owns them. */
export function useStagedCells(store: JotaiStore) {
  const { addStagedCell, removeStagedCell } = useStagedAICellsActions();
  const { setCellCode, createCell } = useCellActions();
  const deleteCellCallback = useDeleteCellCallback();

  const createStagedCell = (code: string): CellId => {
    const newCellId = CellId.create();
    addStagedCell({ cellId: newCellId, edit: { type: "add_cell" } });
    createCell({ code, id: newCellId });
    return newCellId;
  };

  const updateStagedCell = (opts: UpdateStagedCellAction) => {
    const { cellId, code } = opts;
    const stagedAICells = store.get(stagedAICellsAtom);

    if (!stagedAICells.has(cellId)) {
      Logger.error("Staged cell not found", { cellId });
      return;
    }

    writeCellCode(cellId, code);
  };

  // The AI may change the cell's language, and only the editor infers one.
  // Without a mounted editor (e.g. in a collapsed section) the code goes
  // through the document instead.
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

  return {
    createStagedCell,
    updateStagedCell,
    addStagedCell,
    removeStagedCell,
    deleteStagedCell,
    acceptStagedCell,
    rejectStagedCell,
  };
}

export { stagedAICellsAtom };
export const visibleForTesting = {
  createActions,
  reducer,
  initialState,
};
