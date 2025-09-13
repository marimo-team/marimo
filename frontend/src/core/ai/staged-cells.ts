/* Copyright 2024 Marimo. All rights reserved. */

import type { UIMessageChunk } from "ai";
import { useAtomValue } from "jotai";
import { useRef } from "react";
import { useDeleteCellCallback } from "@/components/editor/cell/useDeleteCell";
import { CellId } from "@/core/cells/ids";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { Logger } from "@/utils/Logger";
import { useCellActions } from "../cells/cells";

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

/**
 * Helper functions to create and delete staged cells.
 */
export function useStagedCells() {
  const { addStagedCell, removeStagedCell, clearStagedCells } =
    useStagedAICellsActions();
  const { createNewCell, updateCellCode } = useCellActions();
  const deleteCellCallback = useDeleteCellCallback();
  const stagedAICells = useAtomValue(stagedAICellsAtom);

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

  const updateStagedCell = (cellId: CellId, code: string) => {
    if (!stagedAICells.cellsMap.has(cellId)) {
      Logger.error("Staged cell not found", { cellId });
      return;
    }

    updateCellCode({
      cellId,
      code,
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

class CellCreationStream {
  private lastCellId: CellId | null = null;
  private buffer = "";
  private isInCodeBlock = false;
  private currentCellCode = "";

  private onCreateCell: (code: string) => CellId;
  private onUpdateCell: (cellId: CellId, code: string) => void;

  constructor(
    onCreateCell: (code: string) => CellId,
    onUpdateCell: (cellId: CellId, code: string) => void,
  ) {
    this.onCreateCell = onCreateCell;
    this.onUpdateCell = onUpdateCell;
  }

  stream(chunk: TextDeltaChunk) {
    const delta = chunk.delta;
    this.buffer += delta;

    // Process the buffer to handle code blocks
    this.processBuffer();
  }

  private processBuffer() {
    let processed = false;

    while (!processed) {
      if (this.isInCodeBlock) {
        // Inside code block, looking for closing triple backticks
        const closingMatch = this.buffer.match(/^([^`]*?)`{3,}/);
        if (closingMatch) {
          // Found closing backticks
          this.currentCellCode += closingMatch[1];
          this.buffer = this.buffer.slice(closingMatch[0].length);

          // Create or update the cell
          if (this.lastCellId) {
            this.onUpdateCell(this.lastCellId, this.currentCellCode);
          } else {
            this.lastCellId = this.onCreateCell(this.currentCellCode);
          }

          // Reset state
          this.isInCodeBlock = false;
          this.currentCellCode = "";
          this.lastCellId = null;
        } else {
          // No closing backticks found, add to current cell code
          // Look for closing backticks anywhere in the buffer
          const closingMatch = this.buffer.match(/`{3,}/);
          if (closingMatch) {
            // Found closing backticks, add content before them to cell code
            const beforeBackticks = this.buffer.slice(0, closingMatch.index);
            this.currentCellCode += beforeBackticks;

            // Remove the closing backticks and everything before them from buffer
            this.buffer = this.buffer.slice(
              (closingMatch.index ?? 0) + closingMatch[0].length,
            );

            // Create or update the cell
            if (this.lastCellId) {
              this.onUpdateCell(this.lastCellId, this.currentCellCode);
            } else {
              this.lastCellId = this.onCreateCell(this.currentCellCode);
            }

            // Reset state
            this.isInCodeBlock = false;
            this.currentCellCode = "";
            this.lastCellId = null;
          } else {
            // No closing backticks found, add everything to cell code
            this.currentCellCode += this.buffer;
            this.buffer = "";

            // Update the cell with current content
            if (this.lastCellId) {
              this.onUpdateCell(this.lastCellId, this.currentCellCode);
            } else {
              this.lastCellId = this.onCreateCell(this.currentCellCode);
            }

            processed = true;
          }
        }
      } else {
        // Looking for opening triple backticks
        const backtickMatch = this.buffer.match(
          /^([^`]*?)`{3,}(?:[A-Za-z]*)?\n?/,
        );
        if (backtickMatch) {
          // Found opening backticks, skip the language identifier
          this.buffer = this.buffer.slice(backtickMatch[0].length);
          this.isInCodeBlock = true;
          this.currentCellCode = "";
        } else {
          // No opening backticks found, keep buffering
          processed = true;
        }
      }
    }
  }

  stop() {
    // If we're in a code block when stopping, create/update the cell with remaining content
    if (this.isInCodeBlock && this.currentCellCode) {
      if (this.lastCellId) {
        this.onUpdateCell(this.lastCellId, this.currentCellCode);
      } else {
        this.onCreateCell(this.currentCellCode);
      }
    }

    // Clear all state
    this.lastCellId = null;
    this.buffer = "";
    this.isInCodeBlock = false;
    this.currentCellCode = "";
  }
}

export { stagedAICellsAtom };
export const visibleForTesting = {
  createActions,
  reducer,
  initialState,
  useStagedAICellsActions,
};
