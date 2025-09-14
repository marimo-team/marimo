/* Copyright 2024 Marimo. All rights reserved. */

import type { UIMessageChunk } from "ai";
import { useRef } from "react";
import {
  type AiCompletion,
  codeToCells,
} from "@/components/editor/ai/completion-utils";
import { useDeleteCellCallback } from "@/components/editor/cell/useDeleteCell";
import { CellId } from "@/core/cells/ids";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { Logger } from "@/utils/Logger";
import { useCellActions } from "../cells/cells";
import type { LanguageAdapterType } from "../codemirror/language/types";
import type { JotaiStore } from "../state/jotai";

export interface StagedCellData {
  code: string;
}

/**
 * Cells that are staged for AI completion
 * They function similarly to cells in the notebook, but they can be deleted or accepted by the user.
 * We only track one set of staged cells at a time.
 */
interface StagedAiCells {
  cellsMap: Map<CellId, StagedCellData>;
}

const initialState = (): StagedAiCells => {
  return {
    cellsMap: new Map(),
  };
};

const {
  valueAtom: stagedAICellsAtom,
  useActions: useStagedAICellsActions,
  createActions,
  reducer,
} = createReducerAndAtoms(initialState, {
  addStagedCell: (state, action: { cellId: CellId; code: string }) => {
    const { cellId, code } = action;
    return {
      ...state,
      cellsMap: new Map([...state.cellsMap, [cellId, { code }]]),
    };
  },
  removeStagedCell: (state, cellId: CellId) => {
    return {
      ...state,
      cellsMap: new Map([...state.cellsMap].filter(([id]) => id !== cellId)),
    };
  },
  clearStagedCells: () => {
    return initialState();
  },
});

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
  const { createNewCell, updateCellEditor } = useCellActions();
  const deleteCellCallback = useDeleteCellCallback();

  const cellCreationStream = useRef<CellCreationStream | null>(null);

  const createStagedCell = (code: string): CellId => {
    const newCellId = CellId.create();
    addStagedCell({ cellId: newCellId, code });
    createNewCell({
      cellId: "__end__",
      code,
      before: false,
      newCellId: newCellId,
    });
    return newCellId;
  };

  const updateStagedCell = (opts: UpdateStagedCellAction) => {
    const { cellId, code, language } = opts;
    const stagedAICells = store.get(stagedAICellsAtom);

    if (!stagedAICells.cellsMap.has(cellId)) {
      Logger.error("Staged cell not found", { cellId });
      return;
    }

    updateCellEditor({ cellId, code, language });
  };

  // Delete a staged cell and the corresponding cell in the notebook.
  const deleteStagedCell = (cellId: CellId) => {
    removeStagedCell(cellId);
    deleteCellCallback({ cellId });
  };

  // Delete all staged cells and the corresponding cells in the notebook.
  const deleteAllStagedCells = () => {
    const stagedAICells = store.get(stagedAICellsAtom);
    for (const cellId of stagedAICells.cellsMap.keys()) {
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
      default:
        Logger.error("Unknown chunk type", { chunk });
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

  constructor(
    onCreateCell: (code: string) => CellId,
    onUpdateCell: (opts: UpdateStagedCellAction) => void,
  ) {
    this.onCreateCell = onCreateCell;
    this.onUpdateCell = onUpdateCell;
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

  stop() {
    // Clear all state
    this.buffer = "";
  }
}

export { stagedAICellsAtom };
export const visibleForTesting = {
  createActions,
  reducer,
  initialState,
  useStagedAICellsActions,
};
