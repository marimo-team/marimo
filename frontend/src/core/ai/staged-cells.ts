/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import { useRef } from "react";
import { useDeleteCellCallback } from "@/components/editor/cell/useDeleteCell";
import { CellId } from "@/core/cells/ids";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { Logger } from "@/utils/Logger";
import {
  type CompletionDataPart,
  NOTEBOOK_CELLS_COMPLETION_DATA_TYPE,
  type GeneratedCell,
  notebookCellsCompletionSchema,
} from "./completion-output";
import { maybeAddMarimoImport } from "../cells/add-missing-import";
import {
  type CreateNewCellAction,
  getCellEditorView,
  useCellActions,
} from "../cells/cells";
import { updateEditorCodeFromPython } from "../codemirror/language/utils";
import type { JotaiStore } from "../state/jotai";
import type { EditType } from "./tools/edit-notebook-tool";

/**
 * Cells that are staged for AI completion
 * They function similarly to cells in the notebook, but they can be accepted or rejected by the user.
 * We track edited, new and deleted cells.
 * And we only track one set of staged cells at a time.
 */

export type Edit =
  | { type: Extract<EditType, "update_cell">; previousCode: string }
  | { type: Extract<EditType, "add_cell"> }
  | { type: Extract<EditType, "delete_cell">; previousCode: string };

export type StagedAICells = Map<CellId, Edit>;

export const stagedGenerationInProgressAtom = atom(false);

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
    const newState = new Map(state);
    newState.delete(cellId);
    return newState;
  },
  clearStagedCells: () => {
    return initialState();
  },
});

export {
  useStagedAICellsActions,
  createActions as createStagedAICellsActions,
  reducer as stagedAICellsReducer,
};

interface UpdateStagedCellAction {
  cellId: CellId;
  code: string;
}

/**
 * Helper functions to create and delete staged cells.
 */
export function useStagedCells(store: JotaiStore) {
  const {
    addStagedCell,
    removeStagedCell,
    clearStagedCells: clearStagedCellsState,
  } = useStagedAICellsActions();
  const { createNewCell, updateCellCode } = useCellActions();
  const deleteCellCallback = useDeleteCellCallback();

  const stagedCellReconciler = useRef<StagedCellReconciler | null>(null);

  const clearStagedCells = () => {
    clearStagedCellsState();
    store.set(stagedGenerationInProgressAtom, false);
  };

  const createStagedCell = (code: string): CellId => {
    const newCellId = CellId.create();
    addStagedCell({ cellId: newCellId, edit: { type: "add_cell" } });
    createNewCell({
      cellId: "__end__",
      code,
      before: false,
      newCellId: newCellId,
    });
    return newCellId;
  };

  const updateStagedCell = (opts: UpdateStagedCellAction) => {
    const { cellId, code } = opts;
    const stagedAICells = store.get(stagedAICellsAtom);

    if (!stagedAICells.has(cellId)) {
      Logger.error("Staged cell not found", { cellId });
      return;
    }

    // Update the editor code if the cell is mounted
    // Else, update the cell code in the notebook
    const editorView = getCellEditorView(cellId);
    if (editorView) {
      updateEditorCodeFromPython(editorView, code);
    } else {
      updateCellCode({ cellId, code, formattingChange: false });
    }
  };

  // Delete a staged cell and the corresponding cell in the notebook.
  const deleteStagedCell = (cellId: CellId) => {
    removeStagedCell(cellId);
    deleteCellCallback({ cellId });
  };

  // Delete all staged cells and the corresponding cells in the notebook.
  const deleteAllStagedCells = () => {
    const stagedAICells = store.get(stagedAICellsAtom);
    for (const cellId of stagedAICells.keys()) {
      deleteCellCallback({ cellId });
    }
    clearStagedCellsState();
    store.set(stagedGenerationInProgressAtom, false);
  };

  const beginStagedCellGeneration = () => {
    store.set(stagedGenerationInProgressAtom, true);
    stagedCellReconciler.current = new StagedCellReconciler({
      createStagedCell,
      updateStagedCell,
      deleteStagedCell,
      addStagedCell,
      createNewCell,
    });
  };

  const finishStagedCellGeneration = (successful: boolean) => {
    if (successful) {
      store.set(stagedGenerationInProgressAtom, false);
    } else {
      deleteAllStagedCells();
    }
    stagedCellReconciler.current = null;
  };

  const onData = (part: CompletionDataPart) => {
    if (part.type !== NOTEBOOK_CELLS_COMPLETION_DATA_TYPE) {
      return;
    }
    if (!stagedCellReconciler.current) {
      Logger.error("Staged cell generation not started");
      return;
    }
    const completion = notebookCellsCompletionSchema.parse(part.data);
    stagedCellReconciler.current.reconcile(completion.cells);
  };

  return {
    createStagedCell,
    updateStagedCell,
    addStagedCell,
    removeStagedCell,
    clearStagedCells,
    deleteStagedCell,
    deleteAllStagedCells,
    beginStagedCellGeneration,
    finishStagedCellGeneration,
    onData,
  };
}

export { stagedAICellsAtom };
export const visibleForTesting = {
  createActions,
  reducer,
  initialState,
  useStagedAICellsActions,
};

interface CreatedCell {
  cellId: CellId;
  cell: GeneratedCell;
}

interface StagedCellReconcilerOptions {
  createStagedCell: (code: string) => CellId;
  updateStagedCell: (opts: UpdateStagedCellAction) => void;
  deleteStagedCell: (cellId: CellId) => void;
  addStagedCell: (payload: { cellId: CellId; edit: Edit }) => void;
  createNewCell: (opts: CreateNewCellAction) => void;
}

class StagedCellReconciler {
  private createdCells: CreatedCell[] = [];
  private onCreateCell: (code: string) => CellId;
  private onUpdateCell: (opts: UpdateStagedCellAction) => void;
  private onDeleteCell: (cellId: CellId) => void;
  private addStagedCell: (payload: { cellId: CellId; edit: Edit }) => void;
  private createNewCell: (opts: CreateNewCellAction) => void;
  private marimoImportCellId: CellId | null = null;

  constructor(options: StagedCellReconcilerOptions) {
    this.onCreateCell = options.createStagedCell;
    this.onUpdateCell = options.updateStagedCell;
    this.onDeleteCell = options.deleteStagedCell;
    this.addStagedCell = options.addStagedCell;
    this.createNewCell = options.createNewCell;
  }

  reconcile(completionCells: GeneratedCell[]) {
    for (const [idx, cell] of completionCells.entries()) {
      if (idx < this.createdCells.length) {
        const existingCell = this.createdCells[idx];
        const codeChanged = existingCell.cell.code !== cell.code;
        this.createdCells[idx] = { ...existingCell, cell };
        if (!codeChanged) {
          continue;
        }
        this.onUpdateCell({
          cellId: existingCell.cellId,
          code: cell.code,
        });
      } else {
        const newCellId = this.onCreateCell(cell.code);
        this.createdCells.push({ cellId: newCellId, cell });
      }
    }

    const removedCells = this.createdCells.splice(completionCells.length);
    for (const { cellId } of removedCells.toReversed()) {
      this.onDeleteCell(cellId);
    }

    this.syncMarimoImport(completionCells);
  }

  /** Keep the generated marimo import consistent with the latest snapshot. */
  private syncMarimoImport(completionCells: GeneratedCell[]) {
    const requiresMarimo = completionCells.some(
      (cell) => cell.language !== "python",
    );
    if (!requiresMarimo) {
      if (this.marimoImportCellId) {
        this.onDeleteCell(this.marimoImportCellId);
        this.marimoImportCellId = null;
      }
      return;
    }
    if (this.marimoImportCellId) {
      return;
    }

    const cellId = maybeAddMarimoImport({
      autoInstantiate: false,
      createNewCell: this.createNewCell,
      fromCellId: this.createdCells[0]?.cellId,
      before: true,
    });
    if (cellId) {
      this.addStagedCell({ cellId, edit: { type: "add_cell" } });
      this.marimoImportCellId = cellId;
    }
  }
}
