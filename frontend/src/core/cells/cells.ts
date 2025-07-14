/* Copyright 2024 Marimo. All rights reserved. */

import { historyField } from "@codemirror/commands";
import { type Atom, atom, useAtom, useAtomValue } from "jotai";
import { selectAtom, splitAtom } from "jotai/utils";
import { isEqual, zip } from "lodash-es";
import { createRef, type ReducerWithoutAction } from "react";
import type { CellHandle } from "@/components/editor/Cell";
import {
  type CellColumnId,
  type CellIndex,
  MultiColumn,
} from "@/utils/id-tree";
import { invariant } from "@/utils/invariant";
import { Logger } from "@/utils/Logger";
import { clamp } from "@/utils/math";
import { Objects } from "@/utils/objects";
import { extractAllTracebackInfo, type TracebackInfo } from "@/utils/traceback";
import { createReducerAndAtoms } from "../../utils/createReducer";
import { foldAllBulk, unfoldAllBulk } from "../codemirror/editing/commands";
import {
  splitEditor,
  updateEditorCodeFromPython,
} from "../codemirror/language/utils";
import { findCollapseRange, mergeOutlines } from "../dom/outline";
import type { CellMessage } from "../kernel/messages";
import { isErrorMime } from "../mime";
import type { CellConfig } from "../network/types";
import { isRtcEnabled } from "../rtc/state";
import { createDeepEqualAtom, store } from "../state/jotai";
import { prepareCellForExecution, transitionCell } from "./cell";
import { CellId } from "./ids";
import { type CellLog, getCellLogsForMessage } from "./logs";
import {
  focusAndScrollCellIntoView,
  scrollToBottom,
  scrollToTop,
} from "./scrollCellIntoView";
import {
  type CellData,
  type CellRuntimeState,
  createCell,
  createCellRuntimeState,
} from "./types";
import {
  canUndoDeletes,
  disabledCellIds,
  enabledCellIds,
  notebookIsRunning,
  notebookNeedsRun,
  notebookQueueOrRunningCount,
} from "./utils";

export const SCRATCH_CELL_ID = "__scratch__" as CellId;
export const SETUP_CELL_ID = "setup" as CellId;

export function isSetupCell(cellId: CellId): boolean {
  return cellId === SETUP_CELL_ID;
}

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
   * Array of deleted cells (with their data and index) so that cell deletion can be undone
   *
   * (CodeMirror types the serialized config as any.)
   */
  history: Array<{
    name: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    serializedEditorState: any;
    column: CellColumnId;
    index: CellIndex;
    isSetupCell: boolean;
  }>;
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
}

function withScratchCell(notebookState: NotebookState): NotebookState {
  const config = { column: 0, hide_code: false, disabled: false };
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
function initialNotebookState(): NotebookState {
  return withScratchCell({
    cellIds: MultiColumn.from([]),
    cellData: {},
    cellRuntime: {},
    cellHandles: {},
    history: [],
    scrollKey: null,
    cellLogs: [],
  });
}

/**
 * Actions and reducer for the notebook state.
 */
const {
  reducer,
  createActions,
  useActions,
  valueAtom: notebookAtom,
} = createReducerAndAtoms(initialNotebookState, {
  createNewCell: (
    state,
    action: {
      /** The target cell ID to create a new cell relative to. Can be:
       * - A CellId string for an existing cell
       * - "__end__" to append at the end of the first column
       * - {type: "__end__", columnId} to append at the end of a specific column
       */
      cellId: CellId | "__end__" | { type: "__end__"; columnId: CellColumnId };
      /** Whether to insert before (true) or after (false) the target cell */
      before: boolean;
      /** Initial code content for the new cell */
      code?: string;
      /** The last executed code for the new cell */
      lastCodeRun?: string;
      /** Timestamp of the last execution */
      lastExecutionTime?: number;
      /** Optional custom ID for the new cell. Auto-generated if not provided */
      newCellId?: CellId;
      /** Whether to focus the new cell after creation */
      autoFocus?: boolean;
      /** If true, skip creation if code already exists */
      skipIfCodeExists?: boolean;
    },
  ) => {
    const {
      cellId,
      before,
      code,
      lastCodeRun = null,
      lastExecutionTime = null,
      autoFocus = true,
      skipIfCodeExists = false,
    } = action;

    let columnId: CellColumnId;
    let cellIndex: number;

    // If skipIfCodeExists is true, check if the code already exists in the notebook
    if (skipIfCodeExists) {
      for (const cellId of state.cellIds.inOrderIds) {
        if (state.cellData[cellId]?.code === code) {
          return state;
        }
      }
    }

    if (cellId === "__end__") {
      const column = state.cellIds.atOrThrow(0);
      columnId = column.id;
      cellIndex = column.length;
    } else if (typeof cellId === "string") {
      const column = state.cellIds.findWithId(cellId);
      columnId = column.id;
      cellIndex = column.topLevelIds.indexOf(cellId);
    } else if (cellId.type === "__end__") {
      const column =
        state.cellIds.get(cellId.columnId) || state.cellIds.atOrThrow(0);
      columnId = column.id;
      cellIndex = column.length;
    } else {
      throw new Error("Invalid cellId");
    }

    const newCellId = action.newCellId || CellId.create();
    const insertionIndex = before ? cellIndex : cellIndex + 1;

    return {
      ...state,
      cellIds: state.cellIds.insertId(newCellId, columnId, insertionIndex),
      cellData: {
        ...state.cellData,
        [newCellId]: createCell({
          id: newCellId,
          code,
          lastCodeRun,
          lastExecutionTime,
          edited: Boolean(code) && code !== lastCodeRun,
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
      scrollKey: autoFocus ? newCellId : null,
    };
  },
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
  focusCell: (state, action: { cellId: CellId; before: boolean }) => {
    const column = state.cellIds.findWithId(action.cellId);
    if (column.length === 0) {
      return state;
    }

    const { cellId, before } = action;
    const index = column.indexOfOrThrow(cellId);
    let focusIndex = before ? index - 1 : index + 1;
    // clamp
    focusIndex = clamp(focusIndex, 0, column.length - 1);
    const focusCellId = column.atOrThrow(focusIndex);
    // can scroll immediately, without setting scrollKey in state, because
    // CellArray won't need to re-render
    focusAndScrollCellIntoView({
      cellId: focusCellId,
      cell: state.cellHandles[focusCellId],
      config: state.cellData[focusCellId].config,
      codeFocus: before ? "bottom" : "top",
      variableName: undefined,
    });
    return state;
  },
  focusTopCell: (state) => {
    // TODO: focus the existing column, not the first column
    const column = state.cellIds.getColumns().at(0);
    if (column === undefined || column.length === 0) {
      return state;
    }

    const cellId = column.first();
    focusAndScrollCellIntoView({
      cellId: cellId,
      cell: state.cellHandles[cellId],
      config: state.cellData[cellId].config,
      codeFocus: undefined,
      variableName: undefined,
    });
    scrollToTop();
    return state;
  },
  focusBottomCell: (state) => {
    // TODO: focus the existing column, not the last column
    const column = state.cellIds.getColumns().at(-1);
    if (column === undefined || column.length === 0) {
      return state;
    }

    const cellId = column.last();
    focusAndScrollCellIntoView({
      cellId: cellId,
      cell: state.cellHandles[cellId],
      config: state.cellData[cellId].config,
      codeFocus: undefined,
      variableName: undefined,
    });
    scrollToBottom();
    return state;
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
  deleteCell: (state, action: { cellId: CellId }) => {
    const cellId = action.cellId;

    // Can't delete the last cell, across all columns
    if (state.cellIds.hasOnlyOneId()) {
      return state;
    }

    const column = state.cellIds.findWithId(cellId);
    const cellIndex = column.indexOfOrThrow(cellId);
    const focusIndex = cellIndex === 0 ? 1 : cellIndex - 1;
    let scrollKey: CellId | null = null;
    if (column.length > 1) {
      scrollKey = column.atOrThrow(focusIndex);
    }

    const editorView = state.cellHandles[cellId].current?.editorView;
    const serializedEditorState = editorView?.state.toJSON({
      history: historyField,
    });
    serializedEditorState.doc = state.cellData[cellId].code;

    return {
      ...state,
      cellIds: state.cellIds.deleteById(cellId),
      history: [
        ...state.history,
        {
          name: state.cellData[cellId].name,
          serializedEditorState: serializedEditorState,
          column: column.id,
          index: cellIndex,
          isSetupCell: cellId === SETUP_CELL_ID,
        },
      ],
      scrollKey: scrollKey,
    };
  },
  undoDeleteCell: (state) => {
    if (state.history.length === 0) {
      return state;
    }

    const mostRecentlyDeleted = state.history[state.history.length - 1];

    const {
      name,
      serializedEditorState = { doc: "" },
      column,
      index,
      isSetupCell,
    } = mostRecentlyDeleted;

    const cellId = isSetupCell ? SETUP_CELL_ID : CellId.create();
    const undoCell = createCell({
      id: cellId,
      name,
      code: serializedEditorState.doc,
      edited: serializedEditorState.doc.trim().length > 0,
      serializedEditorState,
    });

    return {
      ...state,
      cellIds: state.cellIds.insertId(cellId, column, index),
      cellData: {
        ...state.cellData,
        [cellId]: undoCell,
      },
      cellRuntime: {
        ...state.cellRuntime,
        [cellId]: createCellRuntimeState(),
      },
      cellHandles: {
        ...state.cellHandles,
        [cellId]: createRef(),
      },
      history: state.history.slice(0, -1),
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
  updateCellName: (state, action: { cellId: CellId; name: string }) => {
    const { cellId, name } = action;
    return updateCellData({
      state,
      cellId,
      cellReducer: (cell) => {
        return {
          ...cell,
          name: name,
        };
      },
    });
  },
  updateCellConfig: (
    state,
    action: { cellId: CellId; config: Partial<CellConfig> },
  ) => {
    const { cellId, config } = action;
    return updateCellData({
      state,
      cellId,
      cellReducer: (cell) => {
        return {
          ...cell,
          config: { ...cell.config, ...config },
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
    const cellId = message.cell_id as CellId;
    const nextState = updateCellRuntimeState({
      state,
      cellId,
      cellReducer: (cell) => {
        return transitionCell(cell, message);
      },
    });
    return {
      ...nextState,
      cellLogs: [...nextState.cellLogs, ...getCellLogsForMessage(message)],
    };
  },
  setCellIds: (state, action: { cellIds: CellId[] }) => {
    const isTheSame = isEqual(state.cellIds.inOrderIds, action.cellIds);
    if (isTheSame) {
      return state;
    }

    // Create new cell data and runtime states for the new cell IDs
    const nextCellData = { ...state.cellData };
    const nextCellRuntime = { ...state.cellRuntime };
    const nextCellHandles = { ...state.cellHandles };

    for (const cellId of action.cellIds) {
      if (!(cellId in state.cellData)) {
        nextCellData[cellId] = createCell({ id: cellId });
      }
      if (!(cellId in state.cellRuntime)) {
        nextCellRuntime[cellId] = createCellRuntimeState();
      }
      if (!(cellId in state.cellHandles)) {
        nextCellHandles[cellId] = createRef();
      }
    }

    return {
      ...state,
      cellIds: MultiColumn.fromWithPreviousShape(action.cellIds, state.cellIds),
      cellData: nextCellData,
      cellRuntime: nextCellRuntime,
      cellHandles: nextCellHandles,
    };
  },
  setCellCodes: (
    state,
    action: { codes: string[]; ids: CellId[]; codeIsStale: boolean },
  ) => {
    invariant(
      action.codes.length === action.ids.length,
      "Expected codes and ids to have the same length",
    );

    let nextState = { ...state };

    const cellReducer = ({
      cell,
      code,
      cellId,
    }: {
      cell: CellData | undefined;
      code: string;
      cellId: CellId;
    }) => {
      if (!cell) {
        return createCell({
          id: cellId,
          code,
          lastCodeRun: action.codeIsStale ? null : code,
          edited: action.codeIsStale && code.trim().length > 0,
        });
      }

      // If code is stale, we don't promote it to lastCodeRun
      const lastCodeRun = action.codeIsStale ? cell.lastCodeRun : code;

      // Mark as edited if the code has changed
      const edited = lastCodeRun
        ? lastCodeRun.trim() !== code.trim()
        : Boolean(code);

      // No change
      if (cell.code.trim() === code.trim()) {
        return {
          ...cell,
          code: code,
          edited,
          lastCodeRun,
        };
      }

      // Update codemirror if mounted
      // If RTC is enabled, the editor view will already be updated, so we don't need to do this
      if (!isRtcEnabled()) {
        const cellHandle = nextState.cellHandles[cellId].current;
        if (cellHandle?.editorViewOrNull) {
          updateEditorCodeFromPython(cellHandle.editorViewOrNull, code);
        }
      }

      return {
        ...cell,
        code: code,
        edited,
        lastCodeRun,
      };
    };

    for (const [cellId, code] of zip(action.ids, action.codes)) {
      if (cellId === undefined || code === undefined) {
        continue;
      }
      nextState = {
        ...nextState,
        cellData: {
          ...nextState.cellData,
          [cellId]: cellReducer({
            cell: nextState.cellData[cellId],
            code,
            cellId,
          }),
        },
      };
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
        if (stdinOutput.channel !== "stdin") {
          Logger.warn("Expected stdin output");
          return cell;
        }

        consoleOutputs[outputIndex] = {
          channel: "stdin",
          mimetype: stdinOutput.mimetype,
          data: stdinOutput.data,
          timestamp: stdinOutput.timestamp,
          response,
        };

        return {
          ...cell,
          interrupted: false,
          consoleOutputs,
        };
      },
    });
  },
  setCells: (state, cells: CellData[]) => {
    const cellData = Object.fromEntries(cells.map((cell) => [cell.id, cell]));

    const cellRuntime = Object.fromEntries(
      cells.map((cell) => [cell.id, createCellRuntimeState()]),
    );

    return withScratchCell({
      ...state,
      cellIds: MultiColumn.fromIdsAndColumns(
        cells.map((cell) => [cell.id, cell.config.column]),
      ),
      cellData: cellData,
      cellRuntime: cellRuntime,
      cellHandles: Object.fromEntries(
        cells.map((cell) => [cell.id, createRef()]),
      ),
    });
  },
  /**
   * Move focus to next cell
   *
   * Creates a new cell if the current cell is the last one in the array.
   *
   * If needed, scrolls newly created or focused cell into view.
   *
   * Replicates Shift+Enter functionality of Jupyter
   */
  moveToNextCell: (
    state,
    action: { cellId: CellId; before: boolean; noCreate?: boolean },
  ) => {
    const { cellId, before, noCreate = false } = action;

    // Can't move focus of scratch cell
    if (cellId === SCRATCH_CELL_ID) {
      return state;
    }

    const column = state.cellIds.findWithId(cellId);
    const index = column.indexOfOrThrow(cellId);
    const nextCellIndex = before ? index - 1 : index + 1;

    const isPastLastCell = nextCellIndex === column.length;
    const isBeforeFirstCell = nextCellIndex === -1;

    // Create a new cell at the end and set scrollKey to focus it
    if (isPastLastCell && !noCreate) {
      const newCellId = CellId.create();
      return {
        ...state,
        cellIds: state.cellIds.insertId(newCellId, column.id, nextCellIndex),
        cellData: {
          ...state.cellData,
          [newCellId]: createCell({ id: newCellId }),
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
    }

    if (isBeforeFirstCell && !noCreate) {
      const newCellId = CellId.create();
      return {
        ...state,
        cellIds: state.cellIds.insertId(newCellId, column.id, 0),
        cellData: {
          ...state.cellData,
          [newCellId]: createCell({ id: newCellId }),
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
    }

    if ((isPastLastCell || isBeforeFirstCell) && noCreate) {
      // Trying to move past the last cell or before the first cell
      // with noCreate=true - do nothing
      return state;
    }

    if (nextCellIndex >= 0 && nextCellIndex < column.length) {
      // Move to valid cell within bounds
      const nextCellId = column.atOrThrow(nextCellIndex);
      // Just focus, no state change
      focusAndScrollCellIntoView({
        cellId: nextCellId,
        cell: state.cellHandles[nextCellId],
        config: state.cellData[nextCellId].config,
        codeFocus: before ? "bottom" : "top",
        variableName: undefined,
      });
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
      config: state.cellData[cellId].config,
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
  collapseCell: (state, action: { cellId: CellId }) => {
    const { cellId } = action;
    const column = state.cellIds.findWithId(cellId);

    // Get all the top-level outlines
    const outlines = column.topLevelIds.map((id) => {
      const cell = state.cellRuntime[id];
      return cell.outline;
    });

    // Find the start/end of the collapsed range
    const startIndex = column.indexOfOrThrow(cellId);
    const range = findCollapseRange(startIndex, outlines);
    if (!range) {
      return state;
    }
    const endCellId = column.atOrThrow(range[1]);

    return {
      ...state,
      // Collapse the range
      cellIds: state.cellIds.transformWithCellId(cellId, (column) =>
        column.collapse(cellId, endCellId),
      ),
      scrollKey: cellId,
    };
  },
  expandCell: (state, action: { cellId: CellId }) => {
    const { cellId } = action;
    return {
      ...state,
      cellIds: state.cellIds.transformWithCellId(cellId, (column) =>
        column.expand(cellId),
      ),
      scrollKey: cellId,
    };
  },
  collapseAllCells: (state) => {
    return {
      ...state,
      cellIds: state.cellIds.transformAll((column) => {
        // Get all the top-level outlines
        const outlines = column.topLevelIds.map((id) => {
          const cell = state.cellRuntime[id];
          return cell.outline;
        });

        // Find the start/end of the collapsed ranges
        const nodes = [...column.nodes];
        const rangeIndexes: Array<{
          start: CellIndex;
          end: CellIndex;
        }> = [];
        const reversedCollapseRanges = [];

        // Iterate in reverse order (bottom-up) to process children first
        let i = nodes.length - 1;
        while (i >= 0) {
          const range = findCollapseRange(i, outlines);
          if (range) {
            const startIndex = i;
            let endIndex = range[1];

            // Check if the parent's end point is inside any already-collapsed child range
            const parentEndInChild = rangeIndexes.find(
              (child) => child.start <= endIndex && child.end === endIndex,
            );

            if (parentEndInChild) {
              // Adjust the new endIndex to the child's start
              endIndex = parentEndInChild.start;
            }

            // Store this range for future child checks
            rangeIndexes.push({ start: startIndex, end: endIndex });

            // Add the range to the list of ranges
            const cellId = column.atOrThrow(startIndex);
            const until = column.atOrThrow(endIndex);
            reversedCollapseRanges.push({ id: cellId, until });
          } else {
            reversedCollapseRanges.push(null);
          }
          i--;
        }

        const collapseRanges = reversedCollapseRanges.reverse();
        return column.collapseAll(collapseRanges);
      }),
    };
  },
  expandAllCells: (state) => {
    return {
      ...state,
      cellIds: state.cellIds.transformAll((column) => column.expandAll()),
    };
  },
  showCellIfHidden: (state, action: { cellId: CellId }) => {
    const { cellId } = action;
    const column = state.cellIds.findWithId(cellId);
    const prev = column;
    const result = column.findAndExpandDeep(cellId);

    if (result.equals(prev)) {
      return state;
    }

    return {
      ...state,
      cellIds: state.cellIds.transformWithCellId(cellId, () => result),
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

    updateEditorCodeFromPython(cellHandle.editorView, beforeCursorCode);

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

    updateEditorCodeFromPython(cellHandle.editorView, snapshot);

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
  upsertSetupCell: (state, action: { code: string }) => {
    const { code } = action;

    // First check if setup cell already exists
    if (SETUP_CELL_ID in state.cellData) {
      // Update existing setup cell
      return updateCellData({
        state,
        cellId: SETUP_CELL_ID,
        cellReducer: (cell) => ({
          ...cell,
          code,
          edited: code.trim() !== cell.lastCodeRun?.trim(),
        }),
      });
    }

    return {
      ...state,
      cellIds: state.cellIds.insertId(
        SETUP_CELL_ID,
        state.cellIds.atOrThrow(0).id,
        0,
      ),
      cellData: {
        ...state.cellData,
        [SETUP_CELL_ID]: createCell({
          id: SETUP_CELL_ID,
          name: SETUP_CELL_ID,
          code,
          edited: Boolean(code),
        }),
      },
      cellRuntime: {
        ...state.cellRuntime,
        [SETUP_CELL_ID]: createCellRuntimeState(),
      },
      cellHandles: {
        ...state.cellHandles,
        [SETUP_CELL_ID]: createRef(),
      },
    };
  },
});

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

  // Handle the case where there's only one column
  // We don't want to set the column config
  const hasMultipleColumns = state.cellIds.getColumns().length > 1;
  if (!hasMultipleColumns) {
    return state.cellIds.getColumns().flatMap((column) => {
      return column.inOrderIds.map((cellId) => {
        return {
          ...cells[cellId].config,
          column: null,
        };
      });
    });
  }

  return state.cellIds.getColumns().flatMap((column, columnIndex) => {
    return column.inOrderIds.map((cellId, cellIndex) => {
      const config: Partial<CellConfig> = { column: undefined };

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

export const needsRunAtom = atom((get) => notebookNeedsRun(get(notebookAtom)));

const cellErrorsAtom = atom((get) => {
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
  const { cellIds, cellRuntime } = get(notebookAtom);
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

export const notebookIsRunningAtom = atom((get) =>
  notebookIsRunning(get(notebookAtom)),
);
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

/**
 * Get the editor views for all cells.
 */
export const getAllEditorViews = () => {
  const { cellIds, cellHandles } = store.get(notebookAtom);
  return cellIds.inOrderIds
    .map((cellId) => cellHandles[cellId]?.current?.editorView)
    .filter(Boolean);
};

export const getCellEditorView = (cellId: CellId) => {
  const { cellHandles } = store.get(notebookAtom);
  return cellHandles[cellId].current?.editorView;
};

export function flattenTopLevelNotebookCells(
  state: NotebookState,
): Array<CellData & CellRuntimeState> {
  const { cellIds, cellData, cellRuntime } = state;
  return cellIds.getColumns().flatMap((column) =>
    column.topLevelIds.map((cellId) => ({
      ...cellData[cellId],
      ...cellRuntime[cellId],
    })),
  );
}

export function createTracebackInfoAtom(
  cellId: CellId,
): Atom<TracebackInfo[] | undefined> {
  // We create an intermediate atom that just computes the string
  // so it prevents downstream recomputations.
  const tracebackStringAtom = atom<string | undefined>((get) => {
    const notebook = get(notebookAtom);
    const data = notebook.cellRuntime[cellId];
    if (!data) {
      return undefined;
    }
    // Must be errored and idle
    if (data.status !== "idle") {
      return undefined;
    }
    const outputs = data.consoleOutputs;
    // console.warn(notebook);
    if (!outputs || outputs.length === 0) {
      return undefined;
    }

    const firstTraceback = outputs.find(
      (output) => output.mimetype === "application/vnd.marimo+traceback",
    );
    if (!firstTraceback) {
      return undefined;
    }
    const traceback = firstTraceback.data;
    return traceback as string;
  });

  return atom((get) => {
    const traceback = get(tracebackStringAtom);
    if (!traceback) {
      return undefined;
    }
    return extractAllTracebackInfo(traceback);
  });
}

/**
 * Use this hook to dispatch cell actions. This hook will not cause a re-render
 * when cells change.
 */
export function useCellActions(): CellActions {
  return useActions();
}

/**
 * Map of cell actions
 */
export type CellActions = ReturnType<typeof createActions>;

/**
 * This is exported for testing purposes only.
 */
export const exportedForTesting = {
  reducer,
  createActions,
  initialNotebookState,
};
