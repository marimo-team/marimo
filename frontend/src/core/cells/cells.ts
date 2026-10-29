/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { type Atom, atom, useAtom, useAtomValue } from "jotai";
import { atomFamily, selectAtom, splitAtom } from "jotai/utils";
import { createRef, type ReducerWithoutAction } from "react";
import type { CellHandle } from "@/components/editor/notebook-cell";
import type { EditableDocument, Placement } from "@/core/notebook/document";
import {
  type CellColumnId,
  type CellIndex,
  MultiColumn,
} from "@/utils/id-tree";
import { invariant } from "@/utils/invariant";
import { Logger } from "@/utils/Logger";
import { Objects } from "@/utils/objects";
import { extractAllTracebackInfo, type TracebackInfo } from "@/utils/traceback";
import { createReducerAndAtoms } from "../../utils/createReducer";
import { foldAllBulk, unfoldAllBulk } from "../codemirror/editing/commands";
import { editorMountScheduler } from "../codemirror/editor-mount-scheduler";
import { prepareCellCodeUpdate } from "../codemirror/language/cell-code";
import { splitEditor } from "../codemirror/language/utils";
import type { SerializedEditorState } from "../codemirror/types";
import { mergeOutlines } from "../dom/outline";
import type { CellMessage } from "../kernel/messages";
import { isErrorMime } from "../mime";
import type { CellConfig } from "../network/types";
import { createDeepEqualAtom, store } from "../state/jotai";
import { isWasm } from "../wasm/utils";
import { prepareCellForExecution, transitionCell } from "./cell";
import { applyDocument, documentEditMiddleware } from "./document";
import { CellId, SCRATCH_CELL_ID } from "./ids";
import { type CellLog, getCellLogsForMessage } from "./logs";
import { focusAndScrollCellIntoView } from "./scrollCellIntoView";
import {
  type CellData,
  type CellRuntimeState,
  createCell,
  createCellRuntimeState,
  isEdited,
} from "./types";
import {
  canUndoDeletes,
  disabledCellIds,
  enabledCellIds,
  getUndoLabel,
  notebookIsRunning,
  notebookNeedsRun,
  notebookQueueOrRunningCount,
} from "./utils";

/** A deleted cell as it was, with where it went in the document. */
export interface DeletedCell {
  cell: Protocol.CellInput;
  placement: Placement;
  /** The editor's state at deletion, so undo brings its history back. */
  serializedEditorState: SerializedEditorState | null;
}

/**
 * History entry for undoing one deletion, of one or more cells.
 */
export interface UndoDeleteEntry {
  type: "delete";
  /** In document order. Each cell is placed after the one before it. */
  cells: DeletedCell[];
}

/**
 * History entry for undoing a cut-paste (move).
 */
export interface UndoMoveEntry {
  type: "move";
  cellIds: CellId[];
  placements: Array<{ columnId: CellColumnId; index: CellIndex }>;
}

export type HistoryEntry = UndoDeleteEntry | UndoMoveEntry;

/**
 * The state of the notebook.
 */
export interface NotebookState {
  /**
   * Order of cells on the page.
   */
  cellIds: MultiColumn<CellId>;
  /**
   * Map of cells to their view state
   */
  cellData: Record<CellId, CellData>;
  /**
   * Map of cells to their runtime state
   */
  cellRuntime: Record<CellId, CellRuntimeState>;
  /**
   * Cell handlers
   */
  cellHandles: Record<CellId, React.RefObject<CellHandle | null>>;
  /**
   * Undo stack: deleted cells and cut-paste moves, in chronological order.
   */
  history: HistoryEntry[];
  /**
   * Key of cell to scroll to; typically set by actions that re-order the cell
   * array. Call the SCROLL_TO_TARGET action to scroll to the specified cell
   * and clear this field.
   */
  scrollKey: CellId | null;
  /**
   * Logs of all cell messages
   */
  cellLogs: CellLog[];
  /**
   * Set of cells that have been created that are initialized with `hide_code`.
   *
   * These start temporarily open until their first blur event.
   */
  untouchedNewCells: Set<CellId>;
}

function withScratchCell(notebookState: NotebookState): NotebookState {
  const config = {
    column: 0,
    hide_code: false,
    disabled: false,
    expand_output: false,
  };
  return {
    ...notebookState,
    cellData: {
      [SCRATCH_CELL_ID]: createCell({ id: SCRATCH_CELL_ID, config: config }),
      ...notebookState.cellData,
    },
    cellRuntime: {
      [SCRATCH_CELL_ID]: createCellRuntimeState(),
      ...notebookState.cellRuntime,
    },
    cellHandles: {
      [SCRATCH_CELL_ID]: createRef(),
      ...notebookState.cellHandles,
    },
  };
}

/**
 * Initial state of the notebook.
 */
export function initialNotebookState(): NotebookState {
  return withScratchCell({
    cellIds: MultiColumn.from([]),
    cellData: {},
    cellRuntime: {},
    cellHandles: {},
    history: [],
    scrollKey: null,
    cellLogs: [],
    untouchedNewCells: new Set<CellId>(),
  });
}

/**
 * Actions and reducer for the notebook state.
 */
const {
  reducer,
  addMiddleware,
  createActions,
  useActions,
  valueAtom: notebookAtom,
} = createReducerAndAtoms(initialNotebookState, {
  moveCell: (
    state,
    action: {
      cellId: CellId;
      before?: boolean;
      direction?: "left" | "right";
    },
  ) => {
    const { cellId, before, direction } = action;

    if (before !== undefined && direction !== undefined) {
      Logger.warn(
        "Both before and direction specified for moveCell. Ignoring one.",
      );
    }

    // Handle left/right movement
    if (direction) {
      const fromColumn = state.cellIds.findWithId(cellId);
      const fromColumnIndex = state.cellIds.indexOf(fromColumn);
      const toColumnIndex =
        direction === "left" ? fromColumnIndex - 1 : fromColumnIndex + 1;
      const toColumn = state.cellIds.at(toColumnIndex);

      // If no column to move to, return unchanged state
      if (!toColumn) {
        return state;
      }

      return {
        ...state,
        cellIds: state.cellIds.moveAcrossColumns(
          fromColumn.id,
          cellId,
          toColumn.id,
          undefined,
        ),
        scrollKey: cellId,
      };
    }

    // Handle up/down movement
    const column = state.cellIds.findWithId(cellId);
    const cellIndex = column.indexOfOrThrow(cellId);

    if (before && cellIndex === 0) {
      return {
        ...state,
        cellIds: state.cellIds.moveWithinColumn(column.id, cellIndex, 0),
        scrollKey: cellId,
      };
    }
    if (!before && cellIndex === column.length - 1) {
      return {
        ...state,
        cellIds: state.cellIds.moveWithinColumn(
          column.id,
          cellIndex,
          column.length - 1,
        ),
        scrollKey: cellId,
      };
    }

    return before
      ? {
          ...state,
          cellIds: state.cellIds.moveWithinColumn(
            column.id,
            cellIndex,
            cellIndex - 1,
          ),
          scrollKey: cellId,
        }
      : {
          ...state,
          cellIds: state.cellIds.moveWithinColumn(
            column.id,
            cellIndex,
            cellIndex + 1,
          ),
          scrollKey: cellId,
        };
  },
  moveCellToIndex: (
    state,
    action: {
      cellId: CellId;
      columnId: CellColumnId;
      index: number;
    },
  ) => {
    const { cellId, columnId, index } = action;
    const fromColumn = state.cellIds.findWithId(cellId);
    const fromIndex = fromColumn.indexOfOrThrow(cellId);

    const destinationColumn = state.cellIds.get(columnId);
    if (!destinationColumn) {
      return state;
    }

    const clampedIndex = Math.max(0, Math.min(index, destinationColumn.length));
    const adjustedIndex =
      fromColumn.id === columnId && fromIndex < clampedIndex
        ? clampedIndex - 1
        : clampedIndex;

    if (fromColumn.id === columnId && fromIndex === adjustedIndex) {
      return state;
    }

    const withoutCell = state.cellIds.deleteById(cellId);
    const updatedColumn = withoutCell.get(columnId);
    if (!updatedColumn) {
      return state;
    }

    return {
      ...state,
      cellIds: withoutCell.insertId(
        cellId,
        columnId,
        Math.max(0, Math.min(adjustedIndex, updatedColumn.length)),
      ),
      scrollKey: null,
    };
  },
  dropCellOverCell: (state, action: { cellId: CellId; overCellId: CellId }) => {
    const { cellId, overCellId } = action;

    const fromColumn = state.cellIds.findWithId(cellId);
    const toColumn = state.cellIds.findWithId(overCellId);

    const fromIndex = fromColumn.indexOfOrThrow(cellId);
    const toIndex = toColumn.indexOfOrThrow(overCellId);

    if (fromColumn.id === toColumn.id) {
      if (fromIndex === toIndex) {
        return state;
      }
      return {
        ...state,
        cellIds: state.cellIds.moveWithinColumn(
          fromColumn.id,
          fromIndex,
          toIndex,
        ),
        scrollKey: null,
      };
    }

    return {
      ...state,
      cellIds: state.cellIds.moveAcrossColumns(
        fromColumn.id,
        cellId,
        toColumn.id,
        overCellId,
      ),
      scrollKey: null,
    };
  },
  moveCellsRelativeTo: (
    state,
    action: {
      cellIds: CellId[];
      targetCellId: CellId;
      position: "before" | "after";
      previousPlacements?: Array<{ columnId: CellColumnId; index: CellIndex }>;
    },
  ) => {
    const { cellIds, targetCellId, position, previousPlacements } = action;
    if (cellIds.length === 0) {
      return state;
    }
    const newCellIds = state.cellIds.moveCellsRelativeTo(
      cellIds,
      targetCellId,
      position,
    );
    // Only record undo when caller provided full before-state
    const canUndoMove =
      previousPlacements && previousPlacements.length === cellIds.length;
    const history = canUndoMove
      ? [
          ...state.history,
          { type: "move" as const, cellIds, placements: previousPlacements },
        ]
      : state.history;
    return {
      ...state,
      cellIds: newCellIds,
      history,
      scrollKey: null,
    };
  },
  dropCellOverColumn: (
    state,
    action: { cellId: CellId; columnId: CellColumnId },
  ) => {
    const { cellId, columnId } = action;
    const fromColumn = state.cellIds.findWithId(cellId);

    return {
      ...state,
      cellIds: state.cellIds.moveAcrossColumns(
        fromColumn.id,
        cellId,
        columnId,
        undefined,
      ),
    };
  },
  dropOverNewColumn: (state, action: { cellId: CellId }) => {
    const { cellId } = action;
    return {
      ...state,
      cellIds: state.cellIds.moveToNewColumn(cellId),
    };
  },
  moveColumn: (
    state,
    action: {
      column: CellColumnId;
      overColumn: CellColumnId | "_left_" | "_right_";
    },
  ) => {
    if (action.column === action.overColumn) {
      return state;
    }
    return {
      ...state,
      cellIds: state.cellIds.moveColumn(action.column, action.overColumn),
    };
  },
  sendToTop: (state, action: { cellId: CellId; scroll?: boolean }) => {
    const column = state.cellIds.findWithId(action.cellId);
    if (column.length === 0) {
      return state;
    }

    const { cellId, scroll = true } = action;
    const cellIndex = column.indexOfOrThrow(cellId);
    if (cellIndex === 0) {
      return state;
    }

    return {
      ...state,
      cellIds: state.cellIds.moveWithinColumn(column.id, cellIndex, 0),
      scrollKey: scroll ? cellId : null,
    };
  },
  sendToBottom: (state, action: { cellId: CellId; scroll?: boolean }) => {
    const column = state.cellIds.findWithId(action.cellId);
    if (column.length === 0) {
      return state;
    }

    const { cellId, scroll = true } = action;
    const cellIndex = column.indexOfOrThrow(cellId);
    const newIndex = column.length - 1;

    if (cellIndex === newIndex) {
      return state;
    }

    return {
      ...state,
      cellIds: state.cellIds.moveWithinColumn(column.id, cellIndex, newIndex),
      scrollKey: scroll ? cellId : null,
    };
  },
  addColumn: (state, action: { columnId: CellColumnId }) => {
    // Add column and new cell
    const newCellId = CellId.create();
    return {
      ...state,
      cellIds: state.cellIds.addColumn(action.columnId, [newCellId]),
      cellData: {
        ...state.cellData,
        [newCellId]: createCell({
          id: newCellId,
        }),
      },
      cellRuntime: {
        ...state.cellRuntime,
        [newCellId]: createCellRuntimeState(),
      },
      cellHandles: {
        ...state.cellHandles,
        [newCellId]: createRef(),
      },
      scrollKey: newCellId,
    };
  },
  addColumnBreakpoint: (state, action: { cellId: CellId }) => {
    const { cellId } = action;
    if (state.cellIds.getColumns()[0].inOrderIds[0] === cellId) {
      return state;
    }
    return {
      ...state,
      cellIds: state.cellIds.insertBreakpoint(cellId),
    };
  },
  deleteColumn: (state, action: { columnId: CellColumnId }) => {
    // Move all cells in the column to the previous column
    const { columnId } = action;
    return {
      ...state,
      cellIds: state.cellIds.delete(columnId),
    };
  },
  mergeAllColumns: (state) => {
    return {
      ...state,
      cellIds: state.cellIds.mergeAllColumns(),
    };
  },
  compactColumns: (state) => {
    return {
      ...state,
      cellIds: state.cellIds.compact(),
    };
  },
  /**
   * Put moved cells back where they were.
   *
   * TODO(MO-8028): Move to `undoDeleteCellAtom` with the order family.
   */
  undoMoveCells: (state, action: UndoMoveEntry) => {
    const { cellIds, placements } = action;
    if (
      cellIds.length === 0 ||
      placements.length !== cellIds.length ||
      cellIds.some((id) => !state.cellData[id])
    ) {
      return state;
    }
    const toRestore = cellIds.map((id, i) => ({
      id,
      columnId: placements[i].columnId,
      index: placements[i].index,
    }));
    return {
      ...state,
      cellIds: state.cellIds.placeCells(toRestore),
      scrollKey: cellIds[0] ?? null,
    };
  },
  clearSerializedEditorState: (state, action: { cellId: CellId }) => {
    const { cellId } = action;
    return updateCellData({
      state,
      cellId,
      cellReducer: (cell) => {
        return {
          ...cell,
          serializedEditorState: null,
        };
      },
    });
  },
  updateCellCode: (
    state,
    action: {
      cellId: CellId;
      code: string;
      /**
       * Whether or not the update is a formatting change,
       * if so, the 'edited' state will be handled differently.
       */
      formattingChange: boolean;
    },
  ) => {
    const { cellId, code, formattingChange } = action;
    if (!state.cellData[cellId]) {
      return state;
    }

    return updateCellData({
      state,
      cellId,
      cellReducer: (cell) => {
        // Formatting-only change means we can re-use the last code run
        // if it was not previously edited. And we don't change the edited state.
        return formattingChange
          ? {
              ...cell,
              code: code,
              lastCodeRun: cell.edited ? cell.lastCodeRun : code,
            }
          : {
              ...cell,
              code: code,
              edited: code.trim() !== cell.lastCodeRun,
            };
      },
    });
  },
  prepareForRun: (state, action: { cellId: CellId }) => {
    const newState = updateCellRuntimeState({
      state,
      cellId: action.cellId,
      cellReducer: (cell) => {
        return prepareCellForExecution(cell);
      },
    });
    return updateCellData({
      state: newState,
      cellId: action.cellId,
      cellReducer: (cell) => {
        return {
          ...cell,
          edited: false,
          lastCodeRun: cell.code.trim(),
        };
      },
    });
  },
  handleCellMessage: (state, message: CellMessage) => {
    const cellId = message.cell_id;
    let nextState = updateCellRuntimeState({
      state,
      cellId,
      cellReducer: (cell) => {
        return transitionCell(cell, message);
      },
    });
    // When a cell is queued for execution, snapshot the current code
    // as lastCodeRun. This clears staleness for cells executed by the
    // kernel (e.g. via code_mode). If the user edits during execution,
    // code !== lastCodeRun keeps the cell stale.
    if (message.status === "queued") {
      nextState = updateCellData({
        state: nextState,
        cellId,
        cellReducer: (cell) => ({
          ...cell,
          lastCodeRun: cell.code.trim(),
          edited: false,
        }),
      });
    }
    return {
      ...nextState,
      cellLogs: [...nextState.cellLogs, ...getCellLogsForMessage(message)],
    };
  },
  addLogs: (state, action: { logs: CellLog[] }) => {
    return {
      ...state,
      cellLogs: [...state.cellLogs, ...action.logs],
    };
  },
  /** Follow the host document's cells and order. */
  reconcileDocument: (state, document: EditableDocument) => {
    const nextState = applyDocument(state, document);
    for (const cellId of state.cellIds.inOrderIds) {
      if (!(cellId in nextState.cellData)) {
        releaseCellAtoms(cellId);
      }
    }
    return nextState;
  },
  setStdinResponse: (
    state,
    action: { cellId: CellId; response: string; outputIndex: number },
  ) => {
    const { cellId, response, outputIndex } = action;
    return updateCellRuntimeState({
      state,
      cellId,
      cellReducer: (cell) => {
        const consoleOutputs = [...cell.consoleOutputs];
        const stdinOutput = consoleOutputs[outputIndex];
        if (stdinOutput == null || stdinOutput.channel !== "stdin") {
          Logger.warn("Expected stdin output");
          return cell;
        }

        consoleOutputs[outputIndex] = {
          channel: "stdin",
          mimetype: stdinOutput.mimetype,
          data: stdinOutput.data,
          timestamp: stdinOutput.timestamp,
          id: stdinOutput.id,
          // An empty response resolves the prompt without retaining the secret.
          response: stdinOutput.mimetype === "text/password" ? "" : response,
        };

        return {
          ...cell,
          interrupted: false,
          consoleOutputs,
        };
      },
    });
  },
  /** Record what the kernel last ran for each cell. */
  setLastRun: (
    state,
    action: {
      lastCodeRun: Record<CellId, string>;
      lastExecutionTime: Record<CellId, number>;
    },
  ) => {
    const cellData = { ...state.cellData };
    for (const cellId of state.cellIds.inOrderIds) {
      const cell = state.cellData[cellId];
      const lastCodeRun = action.lastCodeRun[cellId] ?? null;
      cellData[cellId] = {
        ...cell,
        lastCodeRun,
        lastExecutionTime: action.lastExecutionTime[cellId] ?? null,
        // A cell the kernel never ran is not stale on load.
        edited: lastCodeRun !== null && isEdited(lastCodeRun, cell.code),
      };
    }
    return { ...state, cellData };
  },
  /**
   * Start each cell's runtime over for a new kernel. WASM keeps the outputs
   * its mount-time snapshot gave it.
   */
  resetCellRuntimes: (state) => {
    const preserveSnapshot = isWasm();
    const cellRuntime = { ...state.cellRuntime };
    for (const cellId of state.cellIds.inOrderIds) {
      const previous = state.cellRuntime[cellId];
      const hasSnapshot =
        preserveSnapshot &&
        previous !== undefined &&
        (previous.output != null || previous.consoleOutputs.length > 0);
      cellRuntime[cellId] = hasSnapshot ? previous : createCellRuntimeState();
    }
    return { ...state, cellRuntime };
  },
  markTouched: (state, action: { cellId: CellId }) => {
    const { cellId } = action;

    if (state.untouchedNewCells.has(cellId)) {
      const nextUntouchedNewCells = new Set(state.untouchedNewCells);
      nextUntouchedNewCells.delete(cellId);
      return {
        ...state,
        untouchedNewCells: nextUntouchedNewCells,
      };
    }

    return state;
  },
  markUntouched: (state, action: { cellId: CellId }) => {
    const { cellId } = action;

    if (!state.untouchedNewCells.has(cellId)) {
      const nextUntouchedNewCells = new Set(state.untouchedNewCells);
      nextUntouchedNewCells.add(cellId);
      return {
        ...state,
        untouchedNewCells: nextUntouchedNewCells,
      };
    }

    return state;
  },
  scrollToTarget: (state) => {
    // Scroll to the specified cell and clear the scroll key.
    const scrollKey = state.scrollKey;
    if (scrollKey === null) {
      return state;
    }

    const column = state.cellIds.findWithId(scrollKey);
    const index = column.indexOfOrThrow(scrollKey);

    const cellId =
      index === column.length - 1 ? column.last() : column.atOrThrow(index);

    focusAndScrollCellIntoView({
      cellId: cellId,
      cell: state.cellHandles[cellId],
      isCodeHidden: isCellCodeHidden(state, cellId),
      codeFocus: undefined,
      variableName: undefined,
    });

    return {
      ...state,
      scrollKey: null,
    };
  },
  foldAll: (state) => {
    const targets = Object.values(state.cellHandles).map(
      (handle) => handle.current?.editorView,
    );
    foldAllBulk(targets);
    return state;
  },
  unfoldAll: (state) => {
    const targets = Object.values(state.cellHandles).map(
      (handle) => handle.current?.editorView,
    );
    unfoldAllBulk(targets);
    return state;
  },
  clearLogs: (state) => {
    return {
      ...state,
      cellLogs: [],
    };
  },
  splitCell: (state, action: { cellId: CellId }) => {
    const { cellId } = action;
    const column = state.cellIds.findWithId(cellId);
    const index = column.indexOfOrThrow(cellId);
    const cell = state.cellData[cellId];
    const cellHandle = state.cellHandles[cellId].current;

    if (cellHandle?.editorView == null) {
      return state;
    }

    const { beforeCursorCode, afterCursorCode } = splitEditor(
      cellHandle.editorView,
    );

    const update = prepareCellCodeUpdate(
      cellHandle.editorView.state,
      beforeCursorCode,
    );

    if (update) {
      cellHandle.editorView.dispatch(update);
    }

    const newCellId = CellId.create();

    return {
      ...state,
      cellIds: state.cellIds.insertId(newCellId, column.id, index + 1),
      cellData: {
        ...state.cellData,
        [cellId]: {
          ...cell,
          code: beforeCursorCode,
          edited:
            Boolean(beforeCursorCode) &&
            beforeCursorCode.trim() !== cell.lastCodeRun?.trim(),
        },
        [newCellId]: createCell({
          id: newCellId,
          code: afterCursorCode,
          edited: Boolean(afterCursorCode),
        }),
      },
      cellRuntime: {
        ...state.cellRuntime,
        [cellId]: {
          ...state.cellRuntime[cellId],
          output: null,
          consoleOutputs: [],
        },
        [newCellId]: createCellRuntimeState(),
      },
      cellHandles: {
        ...state.cellHandles,
        [newCellId]: createRef(),
      },
      scrollKey: newCellId,
    };
  },
  undoSplitCell: (state, action: { cellId: CellId; snapshot: string }) => {
    const { cellId, snapshot } = action;

    const cell = state.cellData[cellId];
    const cellHandle = state.cellHandles[cellId].current;

    if (cellHandle?.editorView == null) {
      return state;
    }

    const update = prepareCellCodeUpdate(cellHandle.editorView.state, snapshot);

    if (update) {
      cellHandle.editorView.dispatch(update);
    }

    return {
      ...state,
      cellIds: state.cellIds.transformWithCellId(cellId, (column) => {
        const newCellIndex = column.indexOfOrThrow(cellId) + 1;
        return column.deleteAtIndex(newCellIndex);
      }),
      cellData: {
        ...state.cellData,
        [cellId]: {
          ...cell,
          code: snapshot,
          edited:
            Boolean(snapshot) && snapshot?.trim() !== cell.lastCodeRun?.trim(),
        },
      },
      cellRuntime: {
        ...state.cellRuntime,
        [cellId]: {
          ...state.cellRuntime[cellId],
          output: null,
          consoleOutputs: [],
        },
      },
      cellHandles: {
        ...state.cellHandles,
      },
    };
  },
  clearCellOutput: (state, action: { cellId: CellId }) => {
    const { cellId } = action;
    return updateCellRuntimeState({
      state,
      cellId,
      cellReducer: (cell) => ({
        ...cell,
        output: null,
        consoleOutputs: [],
      }),
    });
  },
  clearCellConsoleOutput: (state, action: { cellId: CellId }) => {
    const { cellId } = action;
    return updateCellRuntimeState({
      state,
      cellId,
      cellReducer: (cell) => ({
        ...cell,
        // Remove everything except unresponsed stdin
        consoleOutputs: cell.consoleOutputs.filter(
          (output) => output.channel === "stdin" && output.response == null,
        ),
      }),
    });
  },
  clearAllCellOutputs: (state) => {
    const newCellRuntime = { ...state.cellRuntime };
    for (const cellId of state.cellIds.inOrderIds) {
      newCellRuntime[cellId] = {
        ...newCellRuntime[cellId],
        output: null,
        consoleOutputs: [],
      };
    }
    return {
      ...state,
      cellRuntime: newCellRuntime,
    };
  },
});

// We apply the middleware here (rather than inline in createReducerAndAtoms)
// so that the document edit middleware can import CellActions and
// strictly type the dispatched actions without creating a circular dependency.
addMiddleware(documentEditMiddleware);

export function isCellCodeHidden(
  state: NotebookState,
  cellId: CellId,
): boolean {
  return (
    Boolean(state.cellData[cellId].config.hide_code) &&
    !state.untouchedNewCells.has(cellId)
  );
}

// Helper function to update a cell in the array
function updateCellRuntimeState({
  state,
  cellId,
  cellReducer,
}: {
  state: NotebookState;
  cellId: CellId;
  cellReducer: ReducerWithoutAction<CellRuntimeState>;
}) {
  if (!(cellId in state.cellRuntime)) {
    Logger.warn(`Cell ${cellId} not found in state`);
    return state;
  }

  return {
    ...state,
    cellRuntime: {
      ...state.cellRuntime,
      [cellId]: cellReducer(state.cellRuntime[cellId]),
    },
  };
}

function updateCellData({
  state,
  cellId,
  cellReducer,
}: {
  state: NotebookState;
  cellId: CellId;
  cellReducer: ReducerWithoutAction<CellData>;
}) {
  if (!(cellId in state.cellData)) {
    Logger.warn(`Cell ${cellId} not found in state`);
    return state;
  }

  return {
    ...state,
    cellData: {
      ...state.cellData,
      [cellId]: cellReducer(state.cellData[cellId]),
    },
  };
}

export function getCellConfigs(state: NotebookState): CellConfig[] {
  const cells = state.cellData;

  // We set to null by default to prevent inconsistencies between undefined & null
  const defaultCellConfig: Partial<CellConfig> = { column: null };

  // Handle the case where there's only one column
  // We don't want to set the column config
  const hasMultipleColumns = state.cellIds.getColumns().length > 1;
  if (!hasMultipleColumns) {
    return state.cellIds.getColumns().flatMap((column) => {
      return column.inOrderIds.map((cellId) => {
        return {
          ...cells[cellId].config,
          ...defaultCellConfig,
        };
      });
    });
  }

  return state.cellIds.getColumns().flatMap((column, columnIndex) => {
    return column.inOrderIds.map((cellId, cellIndex) => {
      const config: Partial<CellConfig> = { ...defaultCellConfig };

      // Only set the column index for the first cell in the column
      if (cellIndex === 0) {
        config.column = columnIndex;
      }

      const newConfig = {
        ...cells[cellId].config,
        ...config,
      };

      return newConfig;
    });
  });
}

export {
  createActions as createNotebookActions,
  reducer as notebookReducer,
  notebookAtom,
};

/** Actions for dispatching outside of React. */
const imperativeActions = createActions((action) => {
  store.set(notebookAtom, (state) => reducer(state, action));
});

export const addLogs = imperativeActions.addLogs;

/// ATOMS

export const cellIdsAtom = atom((get) => get(notebookAtom).cellIds);

export const hasOnlyOneCellAtom = atom((get) =>
  get(cellIdsAtom).hasOnlyOneId(),
);

export const hasDisabledCellsAtom = atom(
  (get) => disabledCellIds(get(notebookAtom)).length > 0,
);
export const hasEnabledCellsAtom = atom(
  (get) => enabledCellIds(get(notebookAtom)).length > 0,
);
export const canUndoDeletesAtom = atom((get) =>
  canUndoDeletes(get(notebookAtom)),
);

export const undoLabelAtom = atom((get) => getUndoLabel(get(notebookAtom)));

export const needsRunAtom = atom((get) => notebookNeedsRun(get(notebookAtom)));

export const cellErrorsAtom = atom((get) => {
  const { cellIds, cellRuntime, cellData } = get(notebookAtom);
  const errors = cellIds.inOrderIds
    .map((cellId) => {
      const cell = cellRuntime[cellId];
      const { name } = cellData[cellId];
      if (isErrorMime(cell.output?.mimetype)) {
        // Filter out ancestor-stopped errors
        // These are errors that are caused by a cell that was stopped,
        // but nothing the user can take action on.
        invariant(Array.isArray(cell.output.data), "Expected array data");
        const nonAncestorErrors = cell.output.data.filter(
          (error) => !error.type.includes("ancestor"),
        );

        if (nonAncestorErrors.length > 0) {
          return {
            output: { ...cell.output, data: nonAncestorErrors },
            cellId: cellId,
            cellName: name,
          };
        }
      }

      return null;
    })
    .filter(Boolean);
  return errors;
});

export const notebookOutline = atom((get) => {
  const cellIds = get(cellIdsAtom);
  const cellRuntime = get(cellsRuntimeAtom);
  const outlines = cellIds.inOrderIds.map(
    (cellId) => cellRuntime[cellId].outline,
  );
  return mergeOutlines(outlines);
});

export const cellErrorCount = atom((get) => get(cellErrorsAtom).length);

export const cellIdToNamesMap = createDeepEqualAtom(
  atom((get) => {
    const { cellIds, cellData } = get(notebookAtom);
    const names: Record<CellId, string | undefined> = Objects.fromEntries(
      cellIds.inOrderIds.map((cellId) => [cellId, cellData[cellId]?.name]),
    );
    return names;
  }),
);

const scrollKeyAtom = atom((get) => get(notebookAtom).scrollKey);

/// HOOKS

/**
 * React-hook for the array of cells.
 */
export const useNotebook = () => useAtomValue(notebookAtom);

/**
 * React-hook for the array of cell IDs.
 */
export const useCellIds = () => useAtomValue(cellIdsAtom);

/**
 * React-hook for the dictionary of cell names
 */
export const useCellNames = () => useAtomValue(cellIdToNamesMap);

/**
 * React-hook for the array of cell errors.
 */
export const useCellErrors = () => useAtomValue(cellErrorsAtom);

/**
 * React-hook for the cell logs.
 */
export const useCellLogs = () => useAtomValue(notebookAtom).cellLogs;

/**
 * React-hook for the notebook scrollKey
 */
export const useScrollKey = () => useAtomValue(scrollKeyAtom);

/// IMPERATIVE GETTERS

/**
 * Get the array of cell IDs.
 */
export const getNotebook = () => store.get(notebookAtom);

/**
 * Get the array of cell IDs.
 */
export const getCells = () => store.get(notebookAtom).cellIds;

/**
 * Get the array of cell names
 */
export const getCellNames = () => {
  const { cellIds, cellData } = store.get(notebookAtom);
  return cellIds.inOrderIds.map((id) => cellData[id]?.name).filter(Boolean);
};

const cellDataAtoms = splitAtom(
  selectAtom(notebookAtom, (cells) =>
    cells.cellIds.inOrderIds.map((id) => cells.cellData[id]),
  ),
);
export const useCellDataAtoms = () => useAtom(cellDataAtoms);

export const cellsRuntimeAtom = atom((get) => get(notebookAtom).cellRuntime);

export const notebookIsRunningAtom = atom((get) =>
  notebookIsRunning(get(notebookAtom)),
);
export const onlyScratchpadIsRunningAtom = atom((get) => {
  const { cellRuntime } = get(notebookAtom);
  return Object.entries(cellRuntime).every(
    ([id, rt]) => rt.status !== "running" || id === SCRATCH_CELL_ID,
  );
});
export const notebookQueuedOrRunningCountAtom = atom((get) =>
  notebookQueueOrRunningCount(get(notebookAtom)),
);

export const numColumnsAtom = atom(
  (get) => get(notebookAtom).cellIds.colLength,
);
export const hasCellsAtom = atom(
  (get) => get(notebookAtom).cellIds.idLength > 0,
);
export const columnIdsAtom = atom((get) =>
  get(notebookAtom).cellIds.getColumnIds(),
);

export const cellDataAtom = atomFamily((cellId: CellId) =>
  atom((get) => get(notebookAtom).cellData[cellId]),
);
const cellRuntimeAtom = atomFamily((cellId: CellId) =>
  atom((get) => get(notebookAtom).cellRuntime[cellId]),
);
export const cellHandleAtom = atomFamily((cellId: CellId) =>
  atom((get) => get(notebookAtom).cellHandles[cellId]),
);
/**
 * Cleans up atomFamily cache entries for the given cell.
 *
 * Jotai's atomFamily retains a cache of created atoms, which can cause memory leaks
 * if not explicitly removed. This function removes the atoms associated with a specific
 * cellId to free up memory.
 *
 * @param cellId - The cell ID whose atoms should be removed.
 * @see https://jotai.org/docs/utilities/family#caveat-memory-leaks
 */
export function releaseCellAtoms(cellId: CellId) {
  cellDataAtom.remove(cellId);
  cellRuntimeAtom.remove(cellId);
  cellHandleAtom.remove(cellId);
}

/** Subscribes to reactive updates of the cell's data. */
export const useCellData = (cellId: CellId) =>
  useAtomValue(cellDataAtom(cellId));
/** Subscribes to reactive updates of the cell's runtime info. */
export const useCellRuntime = (cellId: CellId) =>
  useAtomValue(cellRuntimeAtom(cellId));
/** Subscribes to reactive updates of the cell's handle (e.g. refs or UI bindings). */
export const useCellHandle = (cellId: CellId) =>
  useAtomValue(cellHandleAtom(cellId));

/**
 * Get the editor views for all cells.
 */
export const getAllEditorViews = () => {
  const { cellIds, cellHandles } = store.get(notebookAtom);
  return cellIds.inOrderIds
    .map((cellId) => cellHandles[cellId]?.current?.editorViewOrNull)
    .filter(Boolean);
};

export const getCellEditorView = (cellId: CellId) => {
  const { cellHandles } = store.get(notebookAtom);
  return cellHandles[cellId].current?.editorView;
};

/**
 * Get the cell's editor view. When the view's build is still queued in the
 * progressive-mount scheduler, build it synchronously first. This lets user
 * actions target a cell whose editor is not mounted yet.
 */
export const ensureCellEditorView = (cellId: CellId) => {
  editorMountScheduler.promote(cellId);
  return getCellEditorView(cellId);
};

export function flattenTopLevelNotebookCells(
  state: NotebookState,
): (CellData & CellRuntimeState)[] {
  const { cellIds, cellData, cellRuntime } = state;
  return cellIds.getColumns().flatMap((column) =>
    column.topLevelIds.map((cellId) => ({
      ...cellData[cellId],
      ...cellRuntime[cellId],
    })),
  );
}

export function createUntouchedCellAtom(cellId: CellId): Atom<boolean> {
  return atom((get) => get(notebookAtom).untouchedNewCells.has(cellId));
}

export function createTracebackInfoAtom(
  cellId: CellId,
): Atom<TracebackInfo[] | undefined> {
  //use existing cellRuntimeAtom for intermediate computation
  const cellRuntime = cellRuntimeAtom(cellId);

  return atom((get) => {
    const data = get(cellRuntime);

    if (!data) {
      return undefined;
    }

    if (data.status === "queued" || data.status === "running") {
      return undefined;
    }

    const tracebackInfo: TracebackInfo[] = [];

    // Runtime errors (ZeroDivisionError, etc.)
    const outputs = data.consoleOutputs;
    if (outputs && outputs.length > 0) {
      const firstTraceback = outputs.find(
        (output) => output.mimetype === "application/vnd.marimo+traceback",
      );
      if (firstTraceback) {
        const traceback = firstTraceback.data as string;
        tracebackInfo.push(...extractAllTracebackInfo(traceback));
      }
    }

    // Syntax errors
    const output = data.output;
    if (output?.mimetype === "application/vnd.marimo+error") {
      const errors = output.data;
      if (Array.isArray(errors)) {
        for (const error of errors) {
          if (error.type === "syntax" && error.lineno != null) {
            tracebackInfo.push({
              kind: "cell",
              cellId: cellId,
              lineNumber: error.lineno,
            });
          }
          if (error.type === "import-star" && error.lineno != null) {
            tracebackInfo.push({
              kind: "cell",
              cellId: cellId,
              lineNumber: error.lineno,
            });
          }
        }
      }
    }

    return tracebackInfo.length > 0 ? tracebackInfo : undefined;
  });
}

/** The reducer's actions. Components use `useCellActions` from `./actions`. */
export function useReducerActions(): ReducerCellActions {
  return useActions();
}

/** The actions the reducer still handles. */
export type ReducerCellActions = ReturnType<typeof createActions>;

/**
 * This is exported for testing purposes only.
 */
export const exportedForTesting = {
  reducer,
  createActions,
  initialNotebookState,
  isCellCodeHidden,
  // Export atom families for testing cleanup
  cellDataAtom,
  cellRuntimeAtom,
  cellHandleAtom,
  createTracebackInfoAtom,
};
