/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
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
 * Pending AI edits shared by completion, chat, and agent workflows.
 * Generation ownership keeps one workflow from accepting or discarding another's
 * staged cells.
 */

export type Edit =
  | { type: Extract<EditType, "update_cell">; previousCode: string }
  | { type: Extract<EditType, "add_cell"> }
  | { type: Extract<EditType, "delete_cell">; previousCode: string };

export type StagedAICells = Map<CellId, Edit>;

type StagedGeneration =
  | {
      id: symbol;
      status: "in_progress";
      cellIds: readonly CellId[];
    }
  | { id: symbol; status: "complete" };

interface OwnedStagedGeneration {
  id: symbol;
  status: "in_progress" | "complete";
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
});

export { useStagedAICellsActions };

interface UpdateStagedCellAction {
  cellId: CellId;
  code: string;
}

/** Manage staged cells without assuming which AI workflow owns them. */
export function useStagedCells(store: JotaiStore) {
  const { addStagedCell, removeStagedCell } = useStagedAICellsActions();
  const { createNewCell, updateCellCode } = useCellActions();
  const deleteCellCallback = useDeleteCellCallback();

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

    const editorView = getCellEditorView(cellId);
    if (editorView) {
      updateEditorCodeFromPython(editorView, code);
    } else {
      updateCellCode({ cellId, code, formattingChange: false });
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

/** Owns the lifecycle of cells created by one structured completion flow. */
export function useStagedCellGeneration(store: JotaiStore) {
  const stagedCellActions = useStagedCells(store);
  const { createNewCell } = useCellActions();
  const ownedGeneration = useRef<OwnedStagedGeneration | null>(null);
  // Ownership lives in a ref, so subscribe to its backing atoms to rerender
  // consumers when completion or per-cell acceptance changes.
  useAtomValue(stagedGenerationAtom, { store });
  useAtomValue(stagedAICellsAtom, { store });

  const discardStagedCellIds = (cellIds: readonly CellId[]) => {
    const stagedAICells = store.get(stagedAICellsAtom);
    for (const cellId of cellIds.toReversed()) {
      if (stagedAICells.has(cellId)) {
        stagedCellActions.deleteStagedCell(cellId);
      }
    }
  };

  const beginStagedCellGeneration = () => {
    const activeGeneration = store.get(stagedGenerationAtom);
    if (activeGeneration?.status === "in_progress") {
      discardStagedCellIds(activeGeneration.cellIds);
    }
    ownedGeneration.current?.reconciler.discard(store.get(stagedAICellsAtom));
    const generationId = Symbol("staged-cell-generation");
    ownedGeneration.current = {
      id: generationId,
      status: "in_progress",
      reconciler: new StagedCellReconciler({
        ...stagedCellActions,
        createNewCell,
      }),
    };
    store.set(stagedGenerationAtom, {
      id: generationId,
      status: "in_progress",
      cellIds: [],
    });
  };

  const finishStagedCellGeneration = (successful: boolean) => {
    const generation = ownedGeneration.current;
    if (generation?.status !== "in_progress") {
      return;
    }

    const stagedGeneration = store.get(stagedGenerationAtom);
    const ownsActiveGeneration =
      stagedGeneration?.id === generation.id &&
      stagedGeneration.status === "in_progress";
    if (!ownsActiveGeneration || !successful) {
      generation.reconciler.discard(store.get(stagedAICellsAtom));
      if (ownsActiveGeneration) {
        store.set(stagedGenerationAtom, null);
      }
      ownedGeneration.current = null;
      return;
    }

    generation.status = "complete";
    store.set(stagedGenerationAtom, {
      id: generation.id,
      status: "complete",
    });
  };

  const hasOwnedStagedCells = () => {
    const generation = ownedGeneration.current;
    const stagedGeneration = store.get(stagedGenerationAtom);
    return (
      generation !== null &&
      generation.status === "complete" &&
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
      generation?.status !== "in_progress" ||
      stagedGeneration?.id !== generation.id ||
      stagedGeneration.status !== "in_progress"
    ) {
      return;
    }
    const completion = notebookCellsCompletionSchema.parse(part.data);
    generation.reconciler.reconcile(completion.cells);
    store.set(stagedGenerationAtom, {
      ...stagedGeneration,
      cellIds: generation.reconciler.stagedCellIds(),
    });
  };

  return {
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
};

interface CreatedCell {
  cellId: CellId;
  code: string;
}

interface StagedCellReconcilerActions {
  createStagedCell: (code: string) => CellId;
  updateStagedCell: (opts: UpdateStagedCellAction) => void;
  deleteStagedCell: (cellId: CellId) => void;
  removeStagedCell: (cellId: CellId) => void;
  addStagedCell: (payload: { cellId: CellId; edit: Edit }) => void;
  createNewCell: (opts: CreateNewCellAction) => void;
}

class StagedCellReconciler {
  private createdCells: CreatedCell[] = [];
  private readonly actions: StagedCellReconcilerActions;
  private marimoImportCellId: CellId | null = null;

  constructor(actions: StagedCellReconcilerActions) {
    this.actions = actions;
  }

  reconcile(completionCells: GeneratedCell[]) {
    for (const [idx, cell] of completionCells.entries()) {
      if (idx < this.createdCells.length) {
        const existingCell = this.createdCells[idx];
        const codeChanged = existingCell.code !== cell.code;
        this.createdCells[idx] = { ...existingCell, code: cell.code };
        if (!codeChanged) {
          continue;
        }
        this.actions.updateStagedCell({
          cellId: existingCell.cellId,
          code: cell.code,
        });
      } else {
        const newCellId = this.actions.createStagedCell(cell.code);
        this.createdCells.push({ cellId: newCellId, code: cell.code });
      }
    }

    const removedCells = this.createdCells.splice(completionCells.length);
    for (const { cellId } of removedCells.toReversed()) {
      this.actions.deleteStagedCell(cellId);
    }

    this.syncMarimoImport(completionCells);
  }

  discard(stagedCells: StagedAICells) {
    for (const { cellId } of this.createdCells.toReversed()) {
      if (stagedCells.has(cellId)) {
        this.actions.deleteStagedCell(cellId);
      }
    }
    this.createdCells = [];

    if (this.marimoImportCellId && stagedCells.has(this.marimoImportCellId)) {
      this.actions.deleteStagedCell(this.marimoImportCellId);
    }
    this.marimoImportCellId = null;
  }

  accept() {
    for (const cellId of this.stagedCellIds()) {
      this.actions.removeStagedCell(cellId);
    }
  }

  hasStagedCells(stagedCells: StagedAICells) {
    return this.stagedCellIds().some((cellId) => stagedCells.has(cellId));
  }

  stagedCellIds() {
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
        this.actions.deleteStagedCell(this.marimoImportCellId);
        this.marimoImportCellId = null;
      }
      return;
    }
    if (this.marimoImportCellId) {
      return;
    }

    const cellId = maybeAddMarimoImport({
      autoInstantiate: false,
      createNewCell: this.actions.createNewCell,
      fromCellId: this.createdCells[0]?.cellId,
      before: true,
    });
    if (cellId) {
      this.actions.addStagedCell({ cellId, edit: { type: "add_cell" } });
      this.marimoImportCellId = cellId;
    }
  }
}
