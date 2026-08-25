/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import type { UIMessageChunk } from "ai";
import { useRef } from "react";
import { useDeleteCellCallback } from "@/components/editor/cell/useDeleteCell";
import { CellId } from "@/core/cells/ids";
import { logNever } from "@/utils/assertNever";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { Logger } from "@/utils/Logger";
import {
  type CompletionDataPart,
  isDataChunk,
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
import type { LanguageAdapterType } from "../codemirror/language/types";
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
export type StagedGenerationStatus = "idle" | "streaming" | "complete";

export const stagedGenerationStatusAtom = atom<StagedGenerationStatus>("idle");

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
  language?: LanguageAdapterType;
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

  const cellCreationStream = useRef<CellCreationStream | null>(null);

  const clearStagedCells = () => {
    clearStagedCellsState();
    store.set(stagedGenerationStatusAtom, "idle");
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
    store.set(stagedGenerationStatusAtom, "idle");
  };

  const onStream = (chunk: UIMessageChunk) => {
    switch (chunk.type) {
      case "start":
        store.set(stagedGenerationStatusAtom, "streaming");
        cellCreationStream.current = new CellCreationStream({
          createStagedCell,
          updateStagedCell,
          deleteStagedCell,
          addStagedCell,
          createNewCell,
        });
        break;
      case "text-start":
      case "text-delta":
        // The validated data part is authoritative; text may contain the
        // provider's native or prompted structured-output representation.
        break;
      case "text-end":
        break;
      case "finish":
        if (chunk.finishReason === "stop") {
          store.set(stagedGenerationStatusAtom, "complete");
        } else {
          deleteAllStagedCells();
        }
        cellCreationStream.current = null;
        break;
      case "abort":
      case "error":
        deleteAllStagedCells();
        cellCreationStream.current = null;
        Logger.error("Error", chunk.type, { chunk });
        break;
      case "tool-input-error":
      case "tool-output-error":
        Logger.error("Error", chunk.type, { chunk });
        break;
      case "tool-approval-request":
        Logger.log("Tool approval request", { chunk });
        break;
      case "tool-output-denied":
        Logger.error("Tool output denied", { chunk });
        break;
      // These logs are not useful for debugging
      case "start-step":
      case "finish-step":
      case "data-reasoning-signature":
        break;
      case "message-metadata":
      case "tool-input-available":
      case "tool-output-available":
      case "tool-approval-response":
      case "reasoning-start":
      case "reasoning-delta":
      case "reasoning-end":
      case "file":
      case "reasoning-file":
      case "source-document":
      case "source-url":
      case "tool-input-start":
      case "tool-input-delta":
      case "custom":
        Logger.debug(chunk.type, { chunk });
        break;
      default:
        if (isDataChunk(chunk)) {
          Logger.debug("Data chunk", { chunk });
          break;
        }
        logNever(chunk);
    }
  };

  const onData = (part: CompletionDataPart) => {
    if (part.type !== NOTEBOOK_CELLS_COMPLETION_DATA_TYPE) {
      return;
    }
    if (!cellCreationStream.current) {
      Logger.error("Cell creation stream not found");
      return;
    }
    const completion = notebookCellsCompletionSchema.parse(part.data);
    cellCreationStream.current.update(completion.cells);
  };

  return {
    createStagedCell,
    updateStagedCell,
    addStagedCell,
    removeStagedCell,
    clearStagedCells,
    deleteStagedCell,
    deleteAllStagedCells,
    onStream,
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

interface CellCreationStreamOptions {
  createStagedCell: (code: string) => CellId;
  updateStagedCell: (opts: UpdateStagedCellAction) => void;
  deleteStagedCell: (cellId: CellId) => void;
  addStagedCell: (payload: { cellId: CellId; edit: Edit }) => void;
  createNewCell: (opts: CreateNewCellAction) => void;
}

class CellCreationStream {
  private createdCells: CreatedCell[] = [];
  private onCreateCell: (code: string) => CellId;
  private onUpdateCell: (opts: UpdateStagedCellAction) => void;
  private onDeleteCell: (cellId: CellId) => void;
  private addStagedCell: (payload: { cellId: CellId; edit: Edit }) => void;
  private createNewCell: (opts: CreateNewCellAction) => void;
  private marimoImportCellId: CellId | null = null;

  constructor(options: CellCreationStreamOptions) {
    this.onCreateCell = options.createStagedCell;
    this.onUpdateCell = options.updateStagedCell;
    this.onDeleteCell = options.deleteStagedCell;
    this.addStagedCell = options.addStagedCell;
    this.createNewCell = options.createNewCell;
  }

  update(completionCells: GeneratedCell[]) {
    for (const [idx, cell] of completionCells.entries()) {
      if (idx < this.createdCells.length) {
        const existingCell = this.createdCells[idx];
        this.createdCells[idx] = { ...existingCell, cell };
        this.onUpdateCell({
          cellId: existingCell.cellId,
          code: cell.code,
          language: cell.language,
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
