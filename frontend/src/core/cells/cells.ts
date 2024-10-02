/* Copyright 2024 Marimo. All rights reserved. */
import { atom, useAtom, useAtomValue } from "jotai";
import { type ReducerWithoutAction, createRef } from "react";
import type { CellMessage } from "../kernel/messages";
import {
  type CellRuntimeState,
  type CellData,
  createCell,
  createCellRuntimeState,
} from "./types";
import {
  scrollToBottom,
  scrollToTop,
  focusAndScrollCellIntoView,
} from "./scrollCellIntoView";
import { CellId } from "./ids";
import { prepareCellForExecution, transitionCell } from "./cell";
import { store } from "../state/jotai";
import { createReducerAndAtoms } from "../../utils/createReducer";
import { foldAllBulk, unfoldAllBulk } from "../codemirror/editing/commands";
import { findCollapseRange, mergeOutlines, parseOutline } from "../dom/outline";
import type { CellHandle } from "@/components/editor/Cell";
import { Logger } from "@/utils/Logger";
import { Objects } from "@/utils/objects";
import { splitAtom, selectAtom } from "jotai/utils";
import { isStaticNotebook, parseStaticState } from "../static/static-state";
import { type CellLog, getCellLogsForMessage } from "./logs";
import { deserializeBase64, deserializeJson } from "@/utils/json/base64";
import { historyField } from "@codemirror/commands";
import { clamp } from "@/utils/math";
import type { LayoutState } from "../layout/layout";
import { notebookIsRunning, notebookQueueOrRunningCount } from "./utils";
import {
  splitEditor,
  updateEditorCodeFromPython,
} from "../codemirror/language/utils";
import { invariant } from "@/utils/invariant";
import type {
  CellConfig,
  RuntimeState,
  UpdateCellIdsRequest,
} from "../network/types";
import { getUserConfig } from "@/core/config/config";
import { syncCellIds } from "../network/requests";
import { kioskModeAtom } from "../mode";
import {
  type CellColumnIndex,
  type CellIndex,
  MultiColumn,
} from "@/utils/id-tree";
import { isEqual } from "lodash-es";

export const SCRATCH_CELL_ID = "__scratch__" as CellId;

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
  cellHandles: Record<CellId, React.RefObject<CellHandle>>;
  /**
   * Array of deleted cells (with their data and index) so that cell deletion can be undone
   *
   * (CodeMirror types the serialized config as any.)
   */
  history: Array<{
    name: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    serializedEditorState: any;
    column: CellColumnIndex;
    index: CellIndex;
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

export interface LastSavedNotebook {
  codes: string[];
  configs: CellConfig[];
  names: string[];
  layout: LayoutState;
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
  if (isStaticNotebook()) {
    const {
      cellCodes,
      cellConfigs,
      cellConsoleOutputs,
      cellIds,
      cellNames,
      cellOutputs,
    } = parseStaticState();
    const cellData: Record<CellId, CellData> = {};
    const cellRuntime: Record<CellId, CellRuntimeState> = {};
    for (const [i, cellId] of cellIds.entries()) {
      const name = cellNames[i];
      const code = cellCodes[i];
      const config = cellConfigs[i];
      const outputs = cellConsoleOutputs[cellId] || [];
      const output = cellOutputs[cellId];
      cellData[cellId] = {
        id: cellId,
        name: deserializeBase64(name),
        code: deserializeBase64(code),
        edited: false,
        lastCodeRun: null,
        lastExecutionTime: null,
        config: deserializeJson(deserializeBase64(config)),
        serializedEditorState: null,
      };
      const outputMessage = output
        ? deserializeJson(deserializeBase64(output))
        : null;
      cellRuntime[cellId] = {
        ...createCellRuntimeState(),
        output: outputMessage,
        outline: parseOutline(outputMessage),
        consoleOutputs: outputs.map((output) =>
          deserializeJson(deserializeBase64(output)),
        ),
      };
    }

    return {
      cellIds: MultiColumn.from([cellIds]),
      cellData: cellData,
      cellRuntime: cellRuntime,
      cellHandles: {},
      history: [],
      scrollKey: null,
      cellLogs: [],
    };
  }

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
      cellId: CellId | "__end__";
      before: boolean;
      code?: string;
      lastCodeRun?: string;
      lastExecutionTime?: number;
      newCellId?: CellId;
      autoFocus?: boolean;
    },
  ) => {
    const {
      cellId,
      before,
      code,
      lastCodeRun = null,
      lastExecutionTime = null,
      autoFocus = true,
    } = action;
    const column =
      cellId === "__end__"
        ? state.cellIds.columns[state.cellIds.columns.length - 1]
        : state.cellIds.getColumnWithId(cellId)[0];

    const newCellId = action.newCellId || CellId.create();
    const index =
      cellId === "__end__"
        ? column.length - 1
        : column.topLevelIds.indexOf(cellId);
    const insertionIndex = before ? index : index + 1;
    column.insert(newCellId, insertionIndex);

    return {
      ...state,
      cellData: {
        ...state.cellIds,
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
  moveCell: (state, action: { cellId: CellId; before: boolean }) => {
    const { cellId, before } = action;
    const [column, colIndex] = state.cellIds.getColumnWithId(cellId);
    const cellIndex = column.indexOfOrThrow(cellId);

    if (before && cellIndex === 0) {
      return {
        ...state,
        cellIds: state.cellIds.moveWithinColumn(colIndex, cellIndex, 0),
        scrollKey: cellId,
      };
    }
    if (!before && cellIndex === column.length - 1) {
      return {
        ...state,
        cellIds: state.cellIds.moveWithinColumn(
          colIndex,
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
            colIndex,
            cellIndex,
            cellIndex - 1,
          ),
          scrollKey: cellId,
        }
      : {
          ...state,
          cellIds: state.cellIds.moveWithinColumn(
            colIndex,
            cellIndex,
            cellIndex + 1,
          ),
          scrollKey: cellId,
        };
  },
  dropCellOver: (state, action: { cellId: CellId; overCellId: CellId }) => {
    const { cellId, overCellId } = action;

    const [fromColumn, fromCol] = state.cellIds.getColumnWithId(cellId);
    const fromIndex = fromColumn.indexOfOrThrow(cellId);
    const [toColumn, toCol] = state.cellIds.getColumnWithId(overCellId);
    const toIndex = toColumn.indexOfOrThrow(overCellId);

    if (fromCol === toCol && fromIndex === toIndex) {
      return {
        ...state,
        cellIds: state.cellIds.moveWithinColumn(fromCol, fromIndex, toIndex),
        scrollKey: null,
      };
    }

    return {
      ...state,
      cellIds: state.cellIds.moveAcrossColumns(
        fromCol,
        fromIndex,
        toCol,
        toIndex,
      ),
      scrollKey: null,
    };
  },
  dropOverNewColumn: (state, action: { cellId: CellId }) => {
    const { cellId } = action;
    const [_column, colIndex] = state.cellIds.getColumnWithId(cellId);
    return {
      ...state,
      cellIds: state.cellIds.moveToNewColumn(colIndex, cellId),
    };
  },
  dropColumnOver: (
    state,
    action: { column: CellColumnIndex; overColumn: CellColumnIndex },
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
    const [column, _] = state.cellIds.getColumnWithId(action.cellId);
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
    const column = state.cellIds.columns[0];
    if (column.length === 0) {
      return state;
    }

    const cellId = column.first();
    const cellData = state.cellData[cellId];
    const cellHandle = state.cellHandles[cellId];
    if (!cellData.config.hide_code) {
      cellHandle.current?.editorView.focus();
    }
    scrollToTop();
    return state;
  },
  focusBottomCell: (state) => {
    const column = state.cellIds.columns[state.cellIds.columns.length - 1];
    if (column.length === 0) {
      return state;
    }

    const cellId = column.last();
    const cellData = state.cellData[cellId];
    const cellHandle = state.cellHandles[cellId];
    if (!cellData.config.hide_code) {
      cellHandle.current?.editorView.focus();
    }
    scrollToBottom();
    return state;
  },
  sendToTop: (state, action: { cellId: CellId }) => {
    const [column, colIndex] = state.cellIds.getColumnWithId(action.cellId);
    if (column.length === 0) {
      return state;
    }

    const { cellId } = action;
    const cellIndex = column.indexOfOrThrow(cellId);
    if (cellIndex === 0) {
      return state;
    }

    return {
      ...state,
      cellIds: state.cellIds.moveWithinColumn(colIndex, cellIndex, 0),
      scrollKey: cellId,
    };
  },
  sendToBottom: (state, action: { cellId: CellId }) => {
    const [column, colIndex] = state.cellIds.getColumnWithId(action.cellId);
    if (column.length === 0) {
      return state;
    }

    const { cellId } = action;
    const cellIndex = column.indexOfOrThrow(cellId);
    const newIndex = column.length - 1;

    if (cellIndex === newIndex) {
      return state;
    }

    return {
      ...state,
      cellIds: state.cellIds.moveWithinColumn(colIndex, cellIndex, newIndex),
      scrollKey: cellId,
    };
  },
  addColumnBreakpoint: (state, action: { cellId: CellId }) => {
    const { cellId } = action;
    const [column, colIndex] = state.cellIds.getColumnWithId(cellId);
    if (!column) {
      return state;
    }
    const cellIndex = column.indexOfOrThrow(cellId);
    if (cellIndex === 0) {
      return state;
    }
    return {
      ...state,
      cellIds: state.cellIds.insertBreakpoint(colIndex, cellIndex),
    };
  },
  deleteColumnBreakpoint: (state, action: { columnIndex: CellColumnIndex }) => {
    const { columnIndex } = action;
    return {
      ...state,
      cellIds: state.cellIds.deleteBreakpoint(columnIndex),
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
    const [column, colIndex] = state.cellIds.getColumnWithId(cellId);

    if (column.length === 1) {
      return state;
    }

    const cellIndex = column.indexOfOrThrow(cellId);
    const focusIndex = cellIndex === 0 ? 1 : cellIndex - 1;
    const scrollKey = column.atOrThrow(focusIndex);

    const serializedEditorState = state.cellHandles[
      cellId
    ].current?.editorView.state.toJSON({ history: historyField });

    return {
      ...state,
      cellIds: state.cellIds.deleteId(colIndex, cellIndex),
      history: [
        ...state.history,
        {
          name: state.cellData[cellId].name,
          serializedEditorState: serializedEditorState,
          column: state.cellIds.indexOf(column),
          index: cellIndex,
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
    } = mostRecentlyDeleted;
    const cellId = CellId.create();
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
    return updateCellData(state, cellId, (cell) => {
      return {
        ...cell,
        serializedEditorState: null,
      };
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

    return updateCellData(state, cellId, (cell) => {
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
    });
  },
  updateCellName: (state, action: { cellId: CellId; name: string }) => {
    const { cellId, name } = action;
    return updateCellData(state, cellId, (cell) => {
      return {
        ...cell,
        name: name,
      };
    });
  },
  updateCellConfig: (
    state,
    action: { cellId: CellId; config: Partial<CellConfig> },
  ) => {
    const { cellId, config } = action;
    return updateCellData(state, cellId, (cell) => {
      return {
        ...cell,
        config: { ...cell.config, ...config },
      };
    });
  },
  prepareForRun: (state, action: { cellId: CellId }) => {
    const newState = updateCellRuntimeState(state, action.cellId, (cell) => {
      return prepareCellForExecution(cell);
    });
    return updateCellData(newState, action.cellId, (cell) => {
      return {
        ...cell,
        edited: false,
        lastCodeRun: cell.code.trim(),
        lastExecutionTime: cell.lastExecutionTime,
      };
    });
  },
  handleCellMessage: (state, message: CellMessage) => {
    const cellId = message.cell_id as CellId;
    const nextState = updateCellRuntimeState(state, cellId, (cell) => {
      return transitionCell(cell, message);
    });
    return {
      ...nextState,
      cellLogs: [...nextState.cellLogs, ...getCellLogsForMessage(message)],
    };
  },
  setCellIds: (state, action: { cellIds: CellId[] }) => {
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
      cellIds: MultiColumn.from([action.cellIds]),
      cellData: nextCellData,
      cellRuntime: nextCellRuntime,
      cellHandles: nextCellHandles,
    };
  },
  setCellCodes: (state, action: { codes: string[]; ids: CellId[] }) => {
    invariant(
      action.codes.length === action.ids.length,
      "Expected codes and ids to have the same length",
    );

    for (let i = 0; i < action.codes.length; i++) {
      const cellId = action.ids[i];
      const code = action.codes[i];

      state = updateCellData(state, cellId, (cell) => {
        return {
          ...cell,
          code,
          edited: false,
          lastCodeRun: code,
        };
      });
    }

    return state;
  },
  setStdinResponse: (
    state,
    action: { cellId: CellId; response: string; outputIndex: number },
  ) => {
    const { cellId, response, outputIndex } = action;
    return updateCellRuntimeState(state, cellId, (cell) => {
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
    });
  },
  setCells: (state, cells: CellData[]) => {
    const cellData = Object.fromEntries(cells.map((cell) => [cell.id, cell]));

    const cellRuntime = Object.fromEntries(
      cells.map((cell) => [cell.id, createCellRuntimeState()]),
    );

    let index = 0;
    const columns: CellId[][] = [];

    for (const cell of cells) {
      if (cell.config.column != null) {
        index = cell.config.column;
        columns.push([]);
      }
      columns[index].push(cell.id);
    }

    return withScratchCell({
      ...state,
      cellIds: MultiColumn.from(columns),
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
    const [column, colIndex] = state.cellIds.getColumnWithId(cellId);
    const index = column.indexOfOrThrow(cellId);
    const nextCellIndex = before ? index - 1 : index + 1;
    // Create a new cell at the end; no need to update scrollKey,
    // because cell will be created with autoScrollIntoView
    if (nextCellIndex === column.length && !noCreate) {
      const newCellId = CellId.create();
      return {
        ...state,
        cellIds: state.cellIds.insertId(newCellId, colIndex, nextCellIndex),
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
      };
      // Create a new cell at the beginning; again, no need to update
      // scrollKey
    }

    if (nextCellIndex === -1 && !noCreate) {
      const newCellId = CellId.create();
      return {
        ...state,
        cellIds: state.cellIds.insertId(newCellId, colIndex, 0),
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
      };
    }

    const nextCellId = column.atOrThrow(nextCellIndex);
    // Just focus, no state change
    focusAndScrollCellIntoView({
      cellId: nextCellId,
      cell: state.cellHandles[nextCellId],
      config: state.cellData[nextCellId].config,
      codeFocus: before ? "bottom" : "top",
      variableName: undefined,
    });
    return state;
  },
  scrollToTarget: (state) => {
    // Scroll to the specified cell and clear the scroll key.
    const scrollKey = state.scrollKey;
    if (scrollKey === null) {
      return state;
    }

    const [column, _] = state.cellIds.getColumnWithId(scrollKey);
    const index = column.indexOfOrThrow(scrollKey);

    // Special-case scrolling to the end of the page: bug in Chrome where
    // browser fails to scrollIntoView an element at the end of a long page
    if (index === column.length - 1) {
      const cellId = column.last();
      state.cellHandles[cellId].current?.editorView.focus();
    } else {
      const nextCellId = column.atOrThrow(index);
      focusAndScrollCellIntoView({
        cellId: nextCellId,
        cell: state.cellHandles[nextCellId],
        config: state.cellData[nextCellId].config,
        codeFocus: undefined,
        variableName: undefined,
      });
    }

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
    const [column, colIndex] = state.cellIds.getColumnWithId(cellId);

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

    // Collapse the range
    state.cellIds.columns[colIndex] = column.collapse(cellId, endCellId);

    return {
      ...state,
      scrollKey: cellId,
    };
  },
  expandCell: (state, action: { cellId: CellId }) => {
    const { cellId } = action;
    const [column, colIndex] = state.cellIds.getColumnWithId(cellId);
    state.cellIds.columns[colIndex] = column.expand(cellId);
    return {
      ...state,
      scrollKey: cellId,
    };
  },
  showCellIfHidden: (state, action: { cellId: CellId }) => {
    const { cellId } = action;
    const [column, colIndex] = state.cellIds.getColumnWithId(cellId);
    const prev = column;
    const result = column.findAndExpandDeep(cellId);

    if (result.equals(prev)) {
      return state;
    }

    state.cellIds.columns[colIndex] = result;
    return { ...state };
  },
  splitCell: (state, action: { cellId: CellId }) => {
    const { cellId } = action;
    const [column, colIndex] = state.cellIds.getColumnWithId(cellId);
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
      cellIds: state.cellIds.insertId(newCellId, colIndex, index + 1),
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
    const [column, col] = state.cellIds.getColumnWithId(cellId);
    const newCellIndex = column.indexOfOrThrow(cellId) + 1;
    const cellHandle = state.cellHandles[cellId].current;

    if (cellHandle?.editorView == null) {
      return state;
    }

    updateEditorCodeFromPython(cellHandle.editorView, snapshot);

    return {
      ...state,
      cellIds: state.cellIds.deleteId(col, newCellIndex),
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
});

// Helper function to update a cell in the array
function updateCellRuntimeState(
  state: NotebookState,
  cellId: CellId,
  cellReducer: ReducerWithoutAction<CellRuntimeState>,
) {
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

function updateCellData(
  state: NotebookState,
  cellId: CellId,
  cellReducer: ReducerWithoutAction<CellData>,
) {
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

export function getCellConfigs(state: NotebookState) {
  const cells = state.cellData;
  state.cellIds.columns.forEach((column, columnIndex) => {
    column.inOrderIds.forEach((cellId, cellIndex) => {
      const config: Partial<CellConfig> = { column: undefined };
      if (cellIndex === 0) {
        config.column = columnIndex;
      }
      cells[cellId].config = {
        ...cells[cellId].config,
        ...config,
      };
    });
  });
  return state.cellIds.inOrderIds.map((id) => cells[id].config);
}

export {
  createActions as createNotebookActions,
  reducer as notebookReducer,
  notebookAtom,
};

/// ATOMS

export const cellIdsAtom = atom((get) => get(notebookAtom).cellIds);

export const hasOnlyOneCellAtom = atom(
  (get) =>
    get(cellIdsAtom).columns.length === 1 &&
    get(cellIdsAtom).columns[0].length === 1,
);

const cellErrorsAtom = atom((get) => {
  const { cellIds, cellRuntime, cellData } = get(notebookAtom);
  const errors = cellIds.inOrderIds
    .map((cellId) => {
      const cell = cellRuntime[cellId];
      const { name } = cellData[cellId];
      if (cell.output?.mimetype === "application/vnd.marimo+error") {
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

export const notebookHasCellsAtom = atom(
  (get) =>
    get(cellIdsAtom).columns.length > 0 &&
    get(cellIdsAtom).columns[0].length > 0,
);

export const notebookOutline = atom((get) => {
  const { cellIds, cellRuntime } = get(notebookAtom);
  const outlines = cellIds.inOrderIds.map(
    (cellId) => cellRuntime[cellId].outline,
  );
  return mergeOutlines(outlines);
});

export const cellErrorCount = atom((get) => get(cellErrorsAtom).length);

export const cellIdToNamesMap = atom((get) => {
  const { cellIds, cellData } = get(notebookAtom);
  const names: Record<CellId, string | undefined> = Objects.fromEntries(
    cellIds.inOrderIds.map((cellId) => [cellId, cellData[cellId]?.name]),
  );
  return names;
});

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

/**
 * Get the editor views for all cells.
 */
export const getAllEditorViews = () => {
  const { cellIds, cellHandles } = store.get(notebookAtom);
  return cellIds.inOrderIds
    .map((cellId) => cellHandles[cellId].current?.editorView)
    .filter(Boolean);
};

export const getCellEditorView = (cellId: CellId) => {
  const { cellHandles } = store.get(notebookAtom);
  return cellHandles[cellId].current?.editorView;
};

export function isUninstantiated(
  autoInstantiate: boolean,
  executionTime: number | null,
  status: RuntimeState,
  errored: boolean,
  interrupted: boolean,
  stopped: boolean,
) {
  return (
    // autorun on startup is off ...
    !autoInstantiate &&
    // hasn't run ...
    executionTime === null &&
    // isn't currently queued/running &&
    status !== "queued" &&
    status !== "running" &&
    // and isn't in an error state.
    !(errored || interrupted || stopped)
  );
}

/**
 * Cells that are stale and can be run.
 */
export function staleCellIds(state: NotebookState) {
  const autoInstantiate = getUserConfig().runtime.auto_instantiate;

  const { cellIds, cellData, cellRuntime } = state;
  return cellIds.inOrderIds.filter(
    (cellId) =>
      isUninstantiated(
        autoInstantiate,
        // runElapstedTimeMs is what we've seen in this session
        cellRuntime[cellId].runElapsedTimeMs ??
          // lastExecutionTime is what was seen on session start/resume
          cellData[cellId].lastExecutionTime,
        cellRuntime[cellId].status,
        cellRuntime[cellId].errored,
        cellRuntime[cellId].interrupted,
        cellRuntime[cellId].stopped,
      ) ||
      cellData[cellId].edited ||
      cellRuntime[cellId].interrupted ||
      (cellRuntime[cellId].staleInputs &&
        // if a cell is disabled, it can't be run ...
        !(
          cellRuntime[cellId].status === "disabled-transitively" ||
          cellData[cellId].config.disabled
        )),
  );
}

export function flattenTopLevelNotebookCells(
  state: NotebookState,
): Array<CellData & CellRuntimeState> {
  const { cellIds, cellData, cellRuntime } = state;
  return cellIds.columns.flatMap((column) =>
    column.topLevelIds.map((cellId) => ({
      ...cellData[cellId],
      ...cellRuntime[cellId],
    })),
  );
}

/**
 * Use this hook to dispatch cell actions. This hook will not cause a re-render
 * when cells change.
 */
export function useCellActions() {
  return useActions();
}

/**
 * Map of cell actions
 */
export type CellActions = ReturnType<typeof createActions>;

export const CellEffects = {
  onCellIdsChange: (
    cellIds: MultiColumn<CellId>,
    prevCellIds: MultiColumn<CellId>,
  ) => {
    const kioskMode = store.get(kioskModeAtom);
    if (kioskMode) {
      return;
    }
    // If cellIds is empty, return early
    if (cellIds.columns.length === 0) {
      return;
    }
    // If prevCellIds is empty, also return early
    // this means that the notebook was just created
    if (prevCellIds.columns.length === 0) {
      return;
    }

    // If they are different references, send an update to the server
    if (!isEqual(cellIds.inOrderIds, prevCellIds.inOrderIds)) {
      // "name" property is not actually required
      void syncCellIds({
        cell_ids: cellIds.inOrderIds,
      } as unknown as UpdateCellIdsRequest);
    }
  },
};

/**
 * This is exported for testing purposes only.
 */
export const exportedForTesting = {
  reducer,
  createActions,
  initialNotebookState,
};
