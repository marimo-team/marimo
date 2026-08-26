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

interface StagedGeneration {
  id: symbol;
  status: "in_progress" | "complete";
}

interface OwnedStagedGeneration {
  id: symbol;
  active: boolean;
  reconciler: StagedCellReconciler;
}

const stagedGenerationAtom = atom<StagedGeneration | null>(null);
export const stagedGenerationInProgressAtom = atom(
  (get) => get(stagedGenerationAtom)?.status === "in_progress",
);

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
    removeStagedCell: removeStagedCellState,
    clearStagedCells: clearStagedCellsState,
  } = useStagedAICellsActions();
  const { createNewCell, updateCellCode } = useCellActions();
  const deleteCellCallback = useDeleteCellCallback();

  const ownedGeneration = useRef<OwnedStagedGeneration | null>(null);

  const clearStagedCells = () => {
    clearStagedCellsState();
    store.set(stagedGenerationAtom, null);
  };

  const removeStagedCell = (cellId: CellId) => {
    removeStagedCellState(cellId);
    if (store.get(stagedAICellsAtom).size === 0) {
      store.set(stagedGenerationAtom, null);
    }
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
    store.set(stagedGenerationAtom, null);
  };

  const beginStagedCellGeneration = () => {
    deleteAllStagedCells();
    const generationId = Symbol("staged-cell-generation");
    ownedGeneration.current = {
      id: generationId,
      active: true,
      reconciler: new StagedCellReconciler({
        createStagedCell,
        updateStagedCell,
        deleteStagedCell,
        removeStagedCell,
        addStagedCell,
        createNewCell,
      }),
    };
    store.set(stagedGenerationAtom, {
      id: generationId,
      status: "in_progress",
    });
  };

  const finishStagedCellGeneration = (successful: boolean) => {
    const generation = ownedGeneration.current;
    if (!generation?.active) {
      return;
    }

    const stagedGeneration = store.get(stagedGenerationAtom);
    const ownsActiveGeneration =
      stagedGeneration?.id === generation.id &&
      stagedGeneration.status === "in_progress";

    if (ownsActiveGeneration && !successful) {
      generation.reconciler.discard(store.get(stagedAICellsAtom));
    }
    if (ownsActiveGeneration) {
      store.set(
        stagedGenerationAtom,
        successful ? { id: generation.id, status: "complete" } : null,
      );
    }

    generation.active = false;
    if (!ownsActiveGeneration || !successful) {
      ownedGeneration.current = null;
    }
  };

  const hasOwnedStagedCells = () => {
    const generation = ownedGeneration.current;
    const stagedGeneration = store.get(stagedGenerationAtom);
    return (
      generation !== null &&
      !generation.active &&
      stagedGeneration?.status === "complete" &&
      stagedGeneration.id === generation.id &&
      generation.reconciler.hasStagedCells(store.get(stagedAICellsAtom))
    );
  };

  const acceptOwnedStagedCells = () => {
    if (!hasOwnedStagedCells()) {
      return false;
    }

    ownedGeneration.current?.reconciler.accept();
    store.set(stagedGenerationAtom, null);
    ownedGeneration.current = null;
    return true;
  };

  const discardOwnedStagedCells = () => {
    const generation = ownedGeneration.current;
    const stagedGeneration = store.get(stagedGenerationAtom);
    if (generation === null || stagedGeneration?.id !== generation.id) {
      return false;
    }

    generation.reconciler.discard(store.get(stagedAICellsAtom));
    store.set(stagedGenerationAtom, null);
    ownedGeneration.current = null;
    return true;
  };

  const onData = (part: CompletionDataPart) => {
    if (part.type !== NOTEBOOK_CELLS_COMPLETION_DATA_TYPE) {
      return;
    }
    const generation = ownedGeneration.current;
    const stagedGeneration = store.get(stagedGenerationAtom);
    if (
      !generation?.active ||
      stagedGeneration?.id !== generation.id ||
      stagedGeneration.status !== "in_progress"
    ) {
      return;
    }
    const completion = notebookCellsCompletionSchema.parse(part.data);
    generation.reconciler.reconcile(completion.cells);
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
    hasOwnedStagedCells,
    acceptOwnedStagedCells,
    discardOwnedStagedCells,
    onData,
  };
}

export { stagedAICellsAtom };
export const visibleForTesting = {
  stagedGenerationAtom,
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
  removeStagedCell: (cellId: CellId) => void;
  addStagedCell: (payload: { cellId: CellId; edit: Edit }) => void;
  createNewCell: (opts: CreateNewCellAction) => void;
}

class StagedCellReconciler {
  private createdCells: CreatedCell[] = [];
  private onCreateCell: (code: string) => CellId;
  private onUpdateCell: (opts: UpdateStagedCellAction) => void;
  private onDeleteCell: (cellId: CellId) => void;
  private onRemoveStagedCell: (cellId: CellId) => void;
  private addStagedCell: (payload: { cellId: CellId; edit: Edit }) => void;
  private createNewCell: (opts: CreateNewCellAction) => void;
  private marimoImportCellId: CellId | null = null;

  constructor(options: StagedCellReconcilerOptions) {
    this.onCreateCell = options.createStagedCell;
    this.onUpdateCell = options.updateStagedCell;
    this.onDeleteCell = options.deleteStagedCell;
    this.onRemoveStagedCell = options.removeStagedCell;
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

  discard(stagedCells: StagedAICells) {
    for (const { cellId } of this.createdCells.toReversed()) {
      if (stagedCells.has(cellId)) {
        this.onDeleteCell(cellId);
      }
    }
    this.createdCells = [];

    if (this.marimoImportCellId && stagedCells.has(this.marimoImportCellId)) {
      this.onDeleteCell(this.marimoImportCellId);
    }
    this.marimoImportCellId = null;
  }

  accept() {
    for (const cellId of this.stagedCellIds()) {
      this.onRemoveStagedCell(cellId);
    }
  }

  hasStagedCells(stagedCells: StagedAICells) {
    return this.stagedCellIds().some((cellId) => stagedCells.has(cellId));
  }

  private stagedCellIds() {
    const cellIds = this.createdCells.map(({ cellId }) => cellId);
    if (this.marimoImportCellId) {
      cellIds.push(this.marimoImportCellId);
    }
    return cellIds;
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
