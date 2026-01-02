/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessageChunk } from "ai";
import { useRef } from "react";
import {
  type AiCompletion,
  codeToCells,
} from "@/components/editor/ai/completion-utils";
import { useDeleteCellCallback } from "@/components/editor/cell/useDeleteCell";
import { CellId } from "@/core/cells/ids";
import { logNever } from "@/utils/assertNever";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { Logger } from "@/utils/Logger";
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
  const { addStagedCell, removeStagedCell, clearStagedCells } =
    useStagedAICellsActions();
  const { createNewCell, updateCellCode } = useCellActions();
  const deleteCellCallback = useDeleteCellCallback();

  const cellCreationStream = useRef<CellCreationStream | null>(null);

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
    clearStagedCells();
  };

  const onStream = (chunk: UIMessageChunk) => {
    switch (chunk.type) {
      case "text-start":
        // Create stream
        cellCreationStream.current = new CellCreationStream(
          createStagedCell,
          updateStagedCell,
          addStagedCell,
          createNewCell,
        );
        break;
      case "text-delta":
        if (!cellCreationStream.current) {
          Logger.error("Cell creation stream not found");
          return;
        }
        cellCreationStream.current.stream(chunk);
        break;
      case "text-end":
      case "finish":
        if (!cellCreationStream.current) {
          Logger.error("Cell creation stream not found");
          return;
        }
        cellCreationStream.current.stop();
        break;
      case "abort":
      case "error":
      case "tool-input-error":
      case "tool-output-error":
        Logger.error("Error", chunk.type, { chunk });
        break;
      // These logs are not useful for debugging
      case "start":
      case "start-step":
      case "finish-step":
      case "data-reasoning-signature":
        break;
      case "message-metadata":
      case "tool-input-available":
      case "tool-output-available":
      case "reasoning-start":
      case "reasoning-delta":
      case "reasoning-end":
      case "file":
      case "source-document":
      case "source-url":
      case "tool-input-start":
      case "tool-input-delta":
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

  return {
    createStagedCell,
    updateStagedCell,
    addStagedCell,
    removeStagedCell,
    clearStagedCells,
    deleteStagedCell,
    deleteAllStagedCells,
    onStream,
  };
}

export { stagedAICellsAtom };
export const visibleForTesting = {
  createActions,
  reducer,
  initialState,
  useStagedAICellsActions,
};

type TextDeltaChunk = Extract<UIMessageChunk, { type: "text-delta" }>;

interface CreatedCell {
  cellId: CellId;
  cell: AiCompletion;
}

class CellCreationStream {
  private createdCells: CreatedCell[] = [];
  private buffer = "";

  private onCreateCell: (code: string) => CellId;
  private onUpdateCell: (opts: UpdateStagedCellAction) => void;
  private addStagedCell: (payload: { cellId: CellId; edit: Edit }) => void;
  private createNewCell: (opts: CreateNewCellAction) => void;
  private hasMarimoImport = false;

  constructor(
    onCreateCell: (code: string) => CellId,
    onUpdateCell: (opts: UpdateStagedCellAction) => void,
    addStagedCell: (payload: { cellId: CellId; edit: Edit }) => void,
    createNewCell: (opts: CreateNewCellAction) => void,
  ) {
    this.onCreateCell = onCreateCell;
    this.onUpdateCell = onUpdateCell;
    this.addStagedCell = addStagedCell;
    this.createNewCell = createNewCell;
  }

  stream(chunk: TextDeltaChunk) {
    const delta = chunk.delta;
    this.buffer += delta;
    const completionCells = codeToCells(this.buffer);

    // As incoming chunks are appended to the buffer,
    // we parse the buffer into cells and determine which parts correspond to which cell.
    // For each parsed cell, we either update an existing staged cell or create a new one.
    for (const [idx, cell] of completionCells.entries()) {
      if (idx < this.createdCells.length) {
        this.addMarimoImport(cell.language);
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
  }

  /** Add a marimo import if the cell is SQL or Markdown and we haven't added it yet. */
  private addMarimoImport(language: LanguageAdapterType) {
    if (this.hasMarimoImport || language === "python") {
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
    }
    this.hasMarimoImport = true;
  }

  stop() {
    // Clear all state
    this.buffer = "";
  }
}

type DataChunk = Extract<UIMessageChunk, { type: `data-${string}` }>;

function isDataChunk(chunk: UIMessageChunk): chunk is DataChunk {
  return chunk.type.startsWith("data-");
}
