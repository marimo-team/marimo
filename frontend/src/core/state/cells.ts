/* Copyright 2023 Marimo. All rights reserved. */
import { atom, useAtomValue, useSetAtom } from "jotai";
import { ReducerWithoutAction, createRef, useMemo } from "react";
import { CellMessage } from "../kernel/messages";
import {
  CellConfig,
  CellRuntimeState,
  CellData,
  createCell,
  createCellRuntimeState,
} from "../model/cells";
import {
  scrollToBottom,
  scrollToTop,
  focusAndScrollCellIntoView,
} from "../model/scrollCellIntoView";
import { arrayMove } from "@dnd-kit/sortable";
import { CellId } from "../model/ids";
import { prepareCellForExecution, transitionCell } from "./cell";
import { store } from "./jotai";
import { createReducer } from "../../utils/createReducer";
import { arrayInsert, arrayDelete, arrayShallowEquals } from "@/utils/arrays";
import { foldAllBulk, unfoldAllBulk } from "../codemirror/editing/commands";
import { mergeOutlines } from "../dom/outline";
import { CellHandle } from "@/editor/Cell";
import { Logger } from "@/utils/Logger";
import { Objects } from "@/utils/objects";
import { EditorView } from "@codemirror/view";

/**
 * The state of the notebook.
 */
export interface NotebookState {
  /**
   * Order of cells on the page.
   */
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
  cellHandles: Record<CellId, React.RefObject<CellHandle>>;
  /**
   * Array of deleted cells (with their data and index) so that cell deletion can be undone
   *
   * (CodeMirror types the serialized config as any.)
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  history: Array<{ name: string; serializedEditorState: any; index: number }>;
  /**
   * Key of cell to scroll to; typically set by actions that re-order the cell
   * array. Call the SCROLL_TO_TARGET action to scroll to the specified cell
   * and clear this field.
   */
  scrollKey: CellId | null;
}

/**
 * Initial state of the notebook.
 */
function initialNotebookState(): NotebookState {
  return {
    cellIds: [],
    cellData: {},
    cellRuntime: {},
    cellHandles: {},
    history: [],
    scrollKey: null,
  };
}

/**
 * Actions and reducer for the notebook state.
 */
const { reducer, createActions } = createReducer(initialNotebookState, {
  createNewCell: (state, action: { cellId: CellId; before: boolean }) => {
    const { cellId, before } = action;
    const index = state.cellIds.indexOf(cellId);
    const insertionIndex = before ? index : index + 1;
    const newCellId = CellId.create();

    return {
      ...state,
      cellIds: arrayInsert(state.cellIds, insertionIndex, newCellId),
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
  },
  moveCell: (state, action: { cellId: CellId; before: boolean }) => {
    const { cellId, before } = action;
    const index = state.cellIds.indexOf(cellId);
    const cell = state.cellIds[index];
    if (before && index === 0) {
      return {
        ...state,
        cellIds: [cell, ...state.cellIds.slice(1)],
        scrollKey: cellId,
      };
    } else if (!before && index === state.cellIds.length - 1) {
      return {
        ...state,
        cellIds: [...state.cellIds.slice(0, -1), cell],
        scrollKey: cellId,
      };
    }

    return before
      ? {
          ...state,
          cellIds: arrayMove(state.cellIds, index, index - 1),
          scrollKey: cellId,
        }
      : {
          ...state,
          cellIds: arrayMove(state.cellIds, index, index + 1),
          scrollKey: cellId,
        };
  },
  dropCellOver: (state, action: { cellId: CellId; overCellId: CellId }) => {
    const { cellId, overCellId } = action;
    const fromIndex = state.cellIds.indexOf(cellId);
    const toIndex = state.cellIds.indexOf(overCellId);
    return {
      ...state,
      cellIds: arrayMove(state.cellIds, fromIndex, toIndex),
      scrollKey: null,
    };
  },
  focusCell: (state, action: { cellId: CellId; before: boolean }) => {
    if (state.cellIds.length === 0) {
      return state;
    }

    const { cellId, before } = action;
    const index = state.cellIds.indexOf(cellId);
    let focusIndex = before ? index - 1 : index + 1;
    // clamp
    focusIndex = Math.max(0, Math.min(focusIndex, state.cellIds.length - 1));
    const focusCellId = state.cellIds[focusIndex];
    // can scroll immediately, without setting scrollKey in state, because
    // CellArray won't need to re-render
    focusAndScrollCellIntoView(focusCellId, state.cellHandles[focusCellId]);
    return state;
  },
  focusTopCell: (state) => {
    if (state.cellIds.length === 0) {
      return state;
    }

    const cellKey = state.cellIds[0];
    state.cellHandles[cellKey].current?.editorView.focus();
    scrollToTop();
    return state;
  },
  focusBottomCell: (state) => {
    if (state.cellIds.length === 0) {
      return state;
    }

    const cellKey = state.cellIds[state.cellIds.length - 1];
    state.cellHandles[cellKey].current?.editorView.focus();
    scrollToBottom();
    return state;
  },
  sendToTop: (state, action: { cellId: CellId }) => {
    if (state.cellIds.length === 0) {
      return state;
    }

    const { cellId } = action;
    const index = state.cellIds.indexOf(cellId);
    return {
      ...state,
      cellIds: arrayMove(state.cellIds, index, 0),
      scrollKey: cellId,
    };
  },
  sendToBottom: (state, action: { cellId: CellId }) => {
    if (state.cellIds.length === 0) {
      return state;
    }

    const { cellId } = action;
    const index = state.cellIds.indexOf(cellId);
    return {
      ...state,
      cellIds: arrayMove(state.cellIds, index, state.cellIds.length - 1),
      scrollKey: cellId,
    };
  },
  deleteCell: (state, action: { cellId: CellId }) => {
    const cellId = action.cellId;
    if (state.cellIds.length === 1) {
      return state;
    }

    const index = state.cellIds.indexOf(cellId);
    const cellKey = state.cellIds[index];
    const focusIndex = index === 0 ? 1 : index - 1;
    const scrollKey = state.cellIds[focusIndex];

    return {
      ...state,
      cellIds: arrayDelete(state.cellIds, index),
      history: [
        ...state.history,
        {
          name: state.cellData[cellKey].name,
          serializedEditorState:
            state.cellHandles[cellKey].current?.editorStateJSON(),
          index: index,
        },
      ],
      scrollKey: scrollKey,
    };
  },
  undoDeleteCell: (state) => {
    if (state.history.length === 0) {
      return state;
    } else {
      const mostRecentlyDeleted = state.history[state.history.length - 1];

      const {
        name,
        serializedEditorState = { doc: "" },
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
        cellIds: arrayInsert(state.cellIds, index, cellId),
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
    }
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
    }
  ) => {
    const { cellId, code, formattingChange } = action;
    const cellIndex = state.cellIds.indexOf(cellId);

    if (cellIndex === -1) {
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
  updateCellConfig: (
    state,
    action: { cellId: CellId; config: Partial<CellConfig> }
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
      };
    });
  },
  handleCellMessage: (
    state,
    action: { cellId: CellId; message: CellMessage }
  ) => {
    const { cellId, message } = action;
    return updateCellRuntimeState(state, cellId, (cell) => {
      return transitionCell(cell, message);
    });
  },
  setCells: (state, cells: CellData[]) => {
    return {
      ...state,
      cellIds: cells.map((cell) => cell.id),
      cellData: Object.fromEntries(cells.map((cell) => [cell.id, cell])),
      cellHandles: Object.fromEntries(
        cells.map((cell) => [cell.id, createRef()])
      ),
      cellRuntime: Object.fromEntries(
        cells.map((cell) => [cell.id, createCellRuntimeState()])
      ),
    };
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
  moveToNextCell: (state, action: { cellId: CellId; before: boolean }) => {
    const { cellId, before } = action;
    const index = state.cellIds.indexOf(cellId);
    const nextCellIndex = before ? index - 1 : index + 1;
    // Create a new cell at the end; no need to update scrollKey,
    // because cell will be created with autoScrollIntoView
    if (nextCellIndex === state.cellIds.length) {
      const newCellId = CellId.create();
      return {
        ...state,
        cellIds: [...state.cellIds, newCellId],
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
    } else if (nextCellIndex === -1) {
      const newCellId = CellId.create();
      return {
        ...state,
        cellIds: [newCellId, ...state.cellIds],
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
    } else {
      const nextCellId = state.cellIds[nextCellIndex];
      // Just focus, no state change
      focusAndScrollCellIntoView(nextCellId, state.cellHandles[nextCellId]);
      return state;
    }
  },
  scrollToTarget: (state) => {
    // Scroll to the specified cell and clear the scroll key.
    const scrollKey = state.scrollKey;
    if (scrollKey === null) {
      return state;
    } else {
      const index = state.cellIds.indexOf(scrollKey);

      // Special-case scrolling to the end of the page: bug in Chrome where
      // browser fails to scrollIntoView an element at the end of a long page
      if (index === state.cellIds.length - 1) {
        const cellId = state.cellIds[state.cellIds.length - 1];
        state.cellHandles[cellId].current?.editorView.focus();
        scrollToBottom();
      } else {
        const nextCellId = state.cellIds[index];
        focusAndScrollCellIntoView(nextCellId, state.cellHandles[nextCellId]);
      }

      return {
        ...state,
        scrollKey: null,
      };
    }
  },
  foldAll: (state) => {
    const targets = Object.values(state.cellHandles).map(
      (handle) => handle.current?.editorView
    );
    foldAllBulk(targets);
    return state;
  },
  unfoldAll: (state) => {
    const targets = Object.values(state.cellHandles).map(
      (handle) => handle.current?.editorView
    );
    unfoldAllBulk(targets);
    return state;
  },
});

// Helper function to update a cell in the array
function updateCellRuntimeState(
  state: NotebookState,
  cellId: CellId,
  cellReducer: ReducerWithoutAction<CellRuntimeState>
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
  cellReducer: ReducerWithoutAction<CellData>
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

/// ATOMS

const notebookAtom = atom<NotebookState>(initialNotebookState());

const cellIdsAtom = atom((get) => get(notebookAtom).cellIds);

const cellErrorsAtom = atom((get) => {
  const { cellIds, cellRuntime } = get(notebookAtom);
  const errors = cellIds
    .map((cellId) => {
      const cell = cellRuntime[cellId];
      return cell.output?.mimetype === "application/vnd.marimo+error"
        ? {
            output: cell.output,
            cellId: cellId,
          }
        : null;
    })
    .filter(Boolean);
  return errors;
});

export const notebookOutline = atom((get) => {
  const { cellIds, cellRuntime } = get(notebookAtom);
  const outlines = cellIds.map((cellId) => cellRuntime[cellId].outline);
  return mergeOutlines(outlines);
});

export const cellErrorCount = atom((get) => get(cellErrorsAtom).length);

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
 * React-hook for the array of cell errors.
 */
export const useCellErrors = () => useAtomValue(cellErrorsAtom);

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
 * Get the editor views for all cells.
 */
export const getAllEditorViews = () => {
  const { cellIds, cellHandles } = store.get(notebookAtom);
  return cellIds
    .map((cellId) => cellHandles[cellId].current?.editorView)
    .filter(Boolean);
};

export const getCellEditorView = (cellId: CellId) => {
  const { cellHandles } = store.get(notebookAtom);
  return cellHandles[cellId].current?.editorView;
};

/// HELPERS

export function notebookIsRunning(state: NotebookState) {
  return Object.values(state.cellRuntime).some(
    (cell) => cell.status === "running"
  );
}

export function notebookNeedsSave(
  state: NotebookState,
  otherCodes: string[],
  otherConfigs: CellConfig[]
) {
  const { cellIds, cellData } = state;
  const data = cellIds.map((cellId) => cellData[cellId]);
  const codes = data.map((d) => d.code);
  const configs = data.map((d) => d.config);
  return (
    !arrayShallowEquals(codes, otherCodes) ||
    !arrayShallowEquals(configs, otherConfigs)
  );
}

export function notebookNeedsRun(state: NotebookState) {
  return staleCellIds(state).length > 0;
}

export function notebookCells(state: NotebookState) {
  return state.cellIds.map((cellId) => state.cellData[cellId]);
}

export function notebookCellEditorViews({ cellHandles }: NotebookState) {
  const views: Record<CellId, EditorView> = {};
  for (const [cell, ref] of Objects.entries(cellHandles)) {
    if (!ref.current) {
      continue;
    }
    views[cell] = ref.current.editorView;
  }
  return views;
}

export function disabledCellIds(state: NotebookState) {
  const { cellIds, cellData } = state;
  return cellIds
    .map((cellId) => cellData[cellId])
    .filter((cell) => cell.config.disabled);
}

export function enabledCellIds(state: NotebookState) {
  const { cellIds, cellData } = state;
  return cellIds
    .map((cellId) => cellData[cellId])
    .filter((cell) => !cell.config.disabled);
}

export function staleCellIds(state: NotebookState) {
  const { cellIds, cellData, cellRuntime } = state;
  return cellIds.filter(
    (cellId) => cellData[cellId].edited || cellRuntime[cellId].interrupted
  );
}

export function flattenNotebookCells(state: NotebookState) {
  const { cellIds, cellData, cellRuntime } = state;
  return cellIds.map((cellId) => ({
    ...cellData[cellId],
    ...cellRuntime[cellId],
  }));
}

/**
 * Use this hook to dispatch cell actions. This hook will not cause a re-render
 * when cells change.
 */
export function useCellActions() {
  const setState = useSetAtom(notebookAtom);

  return useMemo(() => {
    const actions = createActions((action) => {
      setState((state) => reducer(state, action));
    });
    return actions;
  }, [setState]);
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
  initialCellState: initialNotebookState,
};
