/* Copyright 2023 Marimo. All rights reserved. */
import { atom, useAtomValue, useSetAtom } from "jotai";
import { ReducerWithoutAction, useMemo } from "react";
import { CellMessage } from "../kernel/messages";
import { CellConfig, CellState, createCell } from "../model/cells";
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
import { arrayInsert, arrayDelete } from "@/utils/arrays";
import { foldAllBulk, unfoldAllBulk } from "../codemirror/editing/commands";

/* The array of cells on the page, together with a history of
 * deleted cells to implement an "undo delete" action
 */
export interface CellsAndHistory {
  /**
   * The array of cells on the page
   */
  present: CellState[];
  /**
   * Tuples of deleted cells, represented by (cell name, serialized editor
   * config, and insertion index), so that cell deletion can be undone
   *
   * (CodeMirror types the serialized config as any.)
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  history: Array<[string, any, number]>;

  /**
   * Key of cell to scroll to; typically set by actions that re-order the cell
   * array. Call the SCROLL_TO_TARGET action to scroll to the specified cell
   * and clear this field.
   */
  scrollKey: CellId | null;
}

function initialCellState(): CellsAndHistory {
  return {
    present: [],
    history: [],
    scrollKey: null,
  };
}

const { reducer, createActions } = createReducer(initialCellState, {
  createNewCell: (state, action: { cellId: CellId; before: boolean }) => {
    const { cellId, before } = action;
    const index = state.present.findIndex((cell) => cell.key === cellId);
    const insertionIndex = before ? index : index + 1;
    const cell = createCell({ key: CellId.create() });

    return {
      ...state,
      present: arrayInsert(state.present, insertionIndex, cell),
      scrollKey: cell.key,
    };
  },
  moveCell: (state, action: { cellId: CellId; before: boolean }) => {
    const { cellId, before } = action;
    const index = state.present.findIndex((cell) => cell.key === cellId);
    const cell = state.present[index];
    if (before && index === 0) {
      return {
        ...state,
        present: [cell, ...state.present.slice(1)],
        scrollKey: cellId,
      };
    } else if (!before && index === state.present.length - 1) {
      return {
        ...state,
        present: [...state.present.slice(0, -1), cell],
        scrollKey: cellId,
      };
    }

    return before
      ? {
          ...state,
          present: arrayMove(state.present, index, index - 1),
          scrollKey: cellId,
        }
      : {
          ...state,
          present: arrayMove(state.present, index, index + 1),
          scrollKey: cellId,
        };
  },
  dropCellOver: (state, action: { cellId: CellId; overCellId: CellId }) => {
    const { cellId, overCellId } = action;
    const fromIndex = state.present.findIndex((cell) => cell.key === cellId);
    const toIndex = state.present.findIndex((cell) => cell.key === overCellId);
    return {
      ...state,
      present: arrayMove(state.present, fromIndex, toIndex),
      scrollKey: null,
    };
  },
  focusCell: (state, action: { cellId: CellId; before: boolean }) => {
    if (state.present.length === 0) {
      return state;
    }

    const { cellId, before } = action;
    const index = state.present.findIndex((cell) => cell.key === cellId);
    let focusIndex = before ? index - 1 : index + 1;
    // clamp
    focusIndex = Math.max(0, Math.min(focusIndex, state.present.length - 1));
    // can scroll immediately, without setting scrollKey in state, because
    // CellArray won't need to re-render
    focusAndScrollCellIntoView(state.present[focusIndex]);
    return state;
  },
  focusTopCell: (state) => {
    if (state.present.length === 0) {
      return state;
    }

    state.present[0].ref.current?.editorView.focus();
    scrollToTop();
    return state;
  },
  focusBottomCell: (state) => {
    if (state.present.length === 0) {
      return state;
    }

    state.present[state.present.length - 1].ref.current?.editorView.focus();
    scrollToBottom();
    return state;
  },
  sendToTop: (state, action: { cellId: CellId }) => {
    if (state.present.length === 0) {
      return state;
    }

    const { cellId } = action;
    const index = state.present.findIndex((cell) => cell.key === cellId);
    return {
      ...state,
      present: arrayMove(state.present, index, 0),
      scrollKey: cellId,
    };
  },
  sendToBottom: (state, action: { cellId: CellId }) => {
    if (state.present.length === 0) {
      return state;
    }

    const { cellId } = action;
    const index = state.present.findIndex((cell) => cell.key === cellId);
    return {
      ...state,
      present: arrayMove(state.present, index, state.present.length - 1),
      scrollKey: cellId,
    };
  },
  deleteCell: (state, action: { cellId: CellId }) => {
    const cellId = action.cellId;
    if (state.present.length === 1) {
      return state;
    }

    const index = state.present.findIndex((cell) => cell.key === cellId);
    const focusIndex = index === 0 ? 1 : index - 1;
    const scrollKey = state.present[focusIndex].key;

    return {
      present: arrayDelete(state.present, index),
      history: [
        ...state.history,
        [
          state.present[index].name,
          state.present[index].ref.current?.editorStateJSON(),
          index,
        ],
      ],
      scrollKey: scrollKey,
    };
  },
  undoDeleteCell: (state) => {
    if (state.history.length === 0) {
      return state;
    } else {
      const mostRecentlyDeleted = state.history[state.history.length - 1];

      const name = mostRecentlyDeleted[0];
      const serializedEditorState = mostRecentlyDeleted[1] || {
        doc: "",
      };
      const index = mostRecentlyDeleted[2];
      const undoCell = createCell({
        key: CellId.create(),
        name,
        initialContents: serializedEditorState.doc,
        code: serializedEditorState.doc,
        edited: serializedEditorState.doc.trim().length > 0,
        serializedEditorState,
      });
      return {
        ...state,
        present: arrayInsert(state.present, index, undoCell),
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
    const cellToUpdate = state.present.find((cell) => cell.key === cellId);

    if (!cellToUpdate || cellToUpdate.code === code) {
      return state;
    }

    return updateCell(state, cellId, (cell) => {
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
    return updateCell(state, cellId, (cell) => {
      return {
        ...cell,
        config: { ...cell.config, ...config },
      };
    });
  },
  prepareForRun: (state, action: { cellId: CellId }) => {
    const cellToUpdate = state.present.find(
      (cell) => cell.key === action.cellId
    );
    if (!cellToUpdate) {
      return state;
    }
    return updateCell(state, action.cellId, (cell) => {
      return prepareCellForExecution(cell);
    });
  },
  handleCellMessage: (
    state,
    action: { cellId: CellId; message: CellMessage }
  ) => {
    const { cellId, message } = action;
    return updateCell(state, cellId, (cell) => {
      return transitionCell(cell, message);
    });
  },
  setCells: (state, cells: CellState[]) => {
    return {
      ...state,
      present: cells,
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
    const index = state.present.findIndex((cell) => cell.key === cellId);
    const nextCellIndex = before ? index - 1 : index + 1;
    // Create a new cell at the end; no need to update scrollKey,
    // because cell will be created with autoScrollIntoView
    if (nextCellIndex === state.present.length) {
      const newCell = createCell({
        key: CellId.create(),
      });
      return {
        ...state,
        present: [...state.present, newCell],
      };
      // Create a new cell at the beginning; again, no need to update
      // scrollKey
    } else if (nextCellIndex === -1) {
      const newCell = createCell({
        key: CellId.create(),
      });
      return {
        ...state,
        present: [newCell, ...state.present],
      };
    } else {
      // Just focus, no state change
      focusAndScrollCellIntoView(state.present[nextCellIndex]);
      return state;
    }
  },
  scrollToTarget: (state) => {
    // Scroll to the specified cell and clear the scroll key.
    const scrollKey = state.scrollKey;
    if (scrollKey === null) {
      return state;
    } else {
      const index = state.present.findIndex((cell) => cell.key === scrollKey);

      // Special-case scrolling to the end of the page: bug in Chrome where
      // browser fails to scrollIntoView an element at the end of a long page
      if (index === state.present.length - 1) {
        state.present[state.present.length - 1].ref.current?.editorView.focus();
        scrollToBottom();
      } else {
        focusAndScrollCellIntoView(state.present[index]);
      }

      return {
        ...state,
        scrollKey: null,
      };
    }
  },
  foldAll: (state) => {
    const targets = state.present.map((cell) => cell.ref.current?.editorView);
    foldAllBulk(targets);
    return state;
  },
  unfoldAll: (state) => {
    const targets = state.present.map((cell) => cell.ref.current?.editorView);
    unfoldAllBulk(targets);
    return state;
  },
});

// Helper function to update a cell in the array
function updateCell(
  state: CellsAndHistory,
  cellId: CellId,
  cellReducer: ReducerWithoutAction<CellState>
) {
  return {
    ...state,
    present: state.present.map((cell) =>
      cell.key === cellId ? cellReducer(cell) : cell
    ),
  };
}

const cellsAtom = atom<CellsAndHistory>(initialCellState());

/**
 * Get the array of cells.
 */
export const useCells = () => useAtomValue(cellsAtom);

/**
 * Get the editor views for all cells.
 */
export const getAllEditorViews = () => {
  const cells = store.get(cellsAtom).present;
  return cells
    .map((cell) => cell.ref.current?.editorView)
    .flatMap((x) => (x ? [x] : []));
};

/**
 * Use this hook to dispatch cell actions. This hook will not cause a re-render
 * when cells change.
 */
export function useCellActions() {
  const setState = useSetAtom(cellsAtom);

  return useMemo(() => {
    const actions = createActions((action) => {
      setState((state) => reducer(state, action));
    });
    return actions;
  }, [setState]);
}

export type CellActions = ReturnType<typeof createActions>;

/**
 * This is exported for testing purposes only.
 */
export const exportedForTesting = {
  reducer,
  createActions,
  initialCellState,
};
