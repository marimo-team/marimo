/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import { type Atom, atom, useAtom, useAtomValue } from "jotai";
import { atomFamily, selectAtom, splitAtom } from "jotai/utils";
import { createRef, type ReducerWithoutAction } from "react";
import type { CellHandle } from "@/components/editor/notebook-cell";
import type { EditableDocument, Placement } from "@/core/notebook/document";
import {
  type CellOutput,
  cellExecutionInputsAtom,
  cellExecutionView,
  cellFreshnessAtom,
  cellOutlineAtom,
  cellOutputAtom,
  releaseCellOutputAtoms,
} from "@/core/executions";
import type { CellColumnId } from "./layout";
import { invariant } from "@/utils/invariant";
import { Logger } from "@/utils/Logger";
import { Objects } from "@/utils/objects";
import { extractAllTracebackInfo, type TracebackInfo } from "@/utils/traceback";
import { createReducerAndAtoms } from "../../utils/createReducer";
import { foldAllBulk, unfoldAllBulk } from "../codemirror/editing/commands";
import { editorMountScheduler } from "../codemirror/editor-mount-scheduler";
import type { SerializedEditorState } from "../codemirror/types";
import { mergeOutlines } from "../dom/outline";
import type { CellMessage } from "../kernel/messages";
import { isErrorMime } from "../mime";
import { createDeepEqualAtom, store } from "../state/jotai";
import { isWasm } from "../wasm/utils";
import { transitionCell } from "./cell";
import { applyDocument } from "./document";
import { isCodeHidden, shownHiddenCodeAtom } from "./editor";
import { type CellId, SCRATCH_CELL_ID } from "./ids";
import { type CellLog, getCellLogsForMessage } from "./logs";
import type { Outline } from "./outline";
import { focusAndScrollCellIntoView } from "./scrollCellIntoView";
import {
  type CellData,
  type CellRuntimeState,
  createCell,
  createCellRuntimeState,
  type RuntimeCell,
} from "./types";
import {
  canUndoDeletes,
  disabledCellIds,
  enabledCellIds,
  getUndoLabel,
  notebookNeedsRun,
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
  placements: Array<{ columnId: CellColumnId; index: number }>;
}

export type HistoryEntry = UndoDeleteEntry | UndoMoveEntry;

/**
 * The state of the notebook.
 */
export interface NotebookState {
  /**
   * Order of cells on the page.
   */
  /** The cells in document order. */
  cellIds: CellId[];
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
    cellIds: [],
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
  prepareForRun: (state, action: { cellId: CellId }) =>
    updateCellRuntimeState({
      state,
      cellId: action.cellId,
      cellReducer: (cell) => ({ ...cell, debuggerActive: false }),
    }),
  handleCellMessage: (state, message: CellMessage) => {
    const cellId = message.cell_id;
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
  addLogs: (state, action: { logs: CellLog[] }) => {
    return {
      ...state,
      cellLogs: [...state.cellLogs, ...action.logs],
    };
  },
  /** Follow the host document's cells and order. */
  reconcileDocument: (state, document: EditableDocument) => {
    const nextState = applyDocument(state, document);
    for (const cellId of state.cellIds) {
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
          input_id: stdinOutput.input_id,
          // An empty response resolves the prompt without retaining the secret.
          response: stdinOutput.mimetype === "text/password" ? "" : response,
        };

        return {
          ...cell,
          consoleOutputs,
        };
      },
    });
  },
  /**
   * Start each cell's runtime over for a new kernel. WASM keeps the console
   * output its mount-time snapshot gave it.
   */
  resetCellRuntimes: (state) => {
    const preserveSnapshot = isWasm();
    const cellRuntime = { ...state.cellRuntime };
    for (const cellId of [...state.cellIds, SCRATCH_CELL_ID]) {
      const previous = state.cellRuntime[cellId];
      const hasSnapshot =
        preserveSnapshot &&
        previous !== undefined &&
        previous.consoleOutputs.length > 0;
      cellRuntime[cellId] = hasSnapshot ? previous : createCellRuntimeState();
    }
    return { ...state, cellRuntime };
  },
  scrollToTarget: (state) => {
    // Scroll to the specified cell and clear the scroll key.
    const scrollKey = state.scrollKey;
    if (scrollKey === null) {
      return state;
    }

    const cellId = scrollKey;
    focusAndScrollCellIntoView({
      cellId: cellId,
      cell: state.cellHandles[cellId],
      isCodeHidden: isCodeHidden(
        state.cellData[cellId]?.config.hide_code,
        store.get(shownHiddenCodeAtom),
        cellId,
      ),
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

export const hasOnlyOneCellAtom = atom((get) => get(cellIdsAtom).length === 1);

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

export const needsRunAtom = atom((get) =>
  notebookNeedsRun(
    get(notebookAtom),
    get(cellExecutionInputsAtom),
    get(cellFreshnessAtom),
  ),
);

export const cellErrorsAtom = atom((get) => {
  const { cellIds, cellData } = get(notebookAtom);
  const errors = cellIds
    .map((cellId) => {
      const output = get(cellOutputAtom(cellId));
      const { name } = cellData[cellId];
      if (output !== null && isErrorMime(output.mimetype)) {
        // Filter out ancestor-stopped errors
        // These are errors that are caused by a cell that was stopped,
        // but nothing the user can take action on.
        invariant(Array.isArray(output.data), "Expected array data");
        const nonAncestorErrors = output.data.filter(
          (error) => !error.type.includes("ancestor"),
        );

        if (nonAncestorErrors.length > 0) {
          return {
            output: { ...output, data: nonAncestorErrors },
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

/**
 * The outline of each cell whose output has a heading. Compared by value, so
 * readers are left alone by the runs that change no heading.
 */
export const cellOutlinesAtom = createDeepEqualAtom(
  atom((get) => {
    const outlines: Partial<Record<CellId, Outline>> = {};
    for (const cellId of get(cellIdsAtom)) {
      const outline = get(cellOutlineAtom(cellId));
      if (outline !== null && outline.items.length > 0) {
        outlines[cellId] = outline;
      }
    }
    return outlines;
  }),
);

/** The notebook's table of contents, in document order. */
export const notebookOutline = atom((get) =>
  mergeOutlines(get(cellIdsAtom).map((cellId) => get(cellOutlineAtom(cellId)))),
);

export const cellErrorCount = atom((get) => get(cellErrorsAtom).length);

export const cellIdToNamesMap = createDeepEqualAtom(
  atom((get) => {
    const { cellIds, cellData } = get(notebookAtom);
    const names: Record<CellId, string | undefined> = Objects.fromEntries(
      cellIds.map((cellId) => [cellId, cellData[cellId]?.name]),
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
  return cellIds.map((id) => cellData[id]?.name).filter(Boolean);
};

const cellDataAtoms = splitAtom(
  selectAtom(notebookAtom, (cells) =>
    cells.cellIds.map((id) => cells.cellData[id]),
  ),
);
export const useCellDataAtoms = () => useAtom(cellDataAtoms);

export const hasCellsAtom = atom((get) => get(notebookAtom).cellIds.length > 0);
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
  releaseCellOutputAtoms(cellId);
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
  return cellIds
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

/** The document's cells with their runtime state and what each shows. */
export function flattenTopLevelNotebookCells(
  state: NotebookState,
  outputs: ReadonlyMap<CellId, CellOutput>,
): RuntimeCell[] {
  const { cellIds, cellData, cellRuntime } = state;
  return cellIds.map((cellId) => ({
    ...cellData[cellId],
    ...cellRuntime[cellId],
    output: outputs.get(cellId) ?? null,
  }));
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

    const { status } = cellExecutionView(get(cellExecutionInputsAtom), cellId);
    if (status === "queued" || status === "running") {
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
    const output = get(cellOutputAtom(cellId));
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
  // Export atom families for testing cleanup
  cellDataAtom,
  cellRuntimeAtom,
  cellHandleAtom,
  createTracebackInfoAtom,
};
