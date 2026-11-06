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

export function useStagedAICell(cellId: CellId): Edit | undefined {
  const stagedCellAtom = useMemo(
    () =>
      selectAtom(stagedAICellsAtom, (cells) => cells.get(cellId), Object.is),
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

    // The AI may change the cell's language, and only the editor infers
    // one. Without a mounted editor the code arrives through the document.
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

  return {
    createStagedCell,
    updateStagedCell,
    addStagedCell,
    removeStagedCell,
    deleteStagedCell,
  };
}

export { stagedAICellsAtom };
export const visibleForTesting = {
  createActions,
  reducer,
  initialState,
};
