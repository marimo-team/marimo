/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { useDeleteCellCallback } from "@/components/editor/cell/useDeleteCell";
import { CellId } from "@/core/cells/ids";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { useCellActions } from "../cells/cells";

/**
 * Cells that are staged for AI completion
 * They function similarly to cells in the notebook, but they can be deleted or accepted by the user.
 * We only track one set of staged cells at a time.
 */
interface StagedAiCells {
  cellIds: Set<CellId>;
}

const initialState = (): StagedAiCells => {
  return {
    cellIds: new Set(),
  };
};

const {
  valueAtom: stagedAICellsAtom,
  useActions: useStagedAICellsActions,
  createActions,
  reducer,
} = createReducerAndAtoms(initialState, {
  addStagedCell: (state, cellId: CellId) => {
    return {
      ...state,
      cellIds: new Set([...state.cellIds, cellId]),
    };
  },
  removeStagedCell: (state, cellId: CellId) => {
    return {
      ...state,
      cellIds: new Set([...state.cellIds].filter((id) => id !== cellId)),
    };
  },
  clearStagedCells: () => {
    return initialState();
  },
});

/**
 * Helper functions to create and delete staged cells.
 */
export function useStagedCells() {
  const { addStagedCell, removeStagedCell, clearStagedCells } =
    useStagedAICellsActions();
  const { createNewCell, updateCellCode } = useCellActions();
  const deleteCellCallback = useDeleteCellCallback();
  const stagedAICells = useAtomValue(stagedAICellsAtom);

  const createStagedCell = (code: string): CellId => {
    const newCellId = CellId.create();
    addStagedCell(newCellId);
    createNewCell({
      cellId: "__end__",
      code: code,
      before: false,
      newCellId: newCellId,
    });
    return newCellId;
  };

  const updateStagedCell = (cellId: CellId, code: string) => {
    if (!stagedAICells.cellIds.has(cellId)) {
      Logger.error("Staged cell not found", { cellId });
      return;
    }

    updateCellCode({
      cellId: cellId,
      code: code,
      formattingChange: false,
    });
  };

  // Delete a staged cell and the corresponding cell in the notebook.
  const deleteStagedCell = (cellId: CellId) => {
    removeStagedCell(cellId);
    deleteCellCallback({ cellId });
  };

  // Delete all staged cells and the corresponding cells in the notebook.
  const deleteAllStagedCells = () => {
    for (const cellId of stagedAICells.cellIds) {
      deleteCellCallback({ cellId });
    }
    clearStagedCells();
  };

  return {
    createStagedCell,
    updateStagedCell,
    addStagedCell,
    removeStagedCell,
    clearStagedCells,
    deleteStagedCell,
    deleteAllStagedCells,
  };
}

export { stagedAICellsAtom };
export const visibleForTesting = {
  createActions,
  reducer,
  initialState,
  useStagedAICellsActions,
};
