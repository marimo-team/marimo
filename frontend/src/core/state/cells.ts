/* Copyright 2023 Marimo. All rights reserved. */
import { atom, useAtomValue, useSetAtom } from "jotai";
import { useMemo } from "react";
import { CellMessage } from "../kernel/messages";
import { CellState, createCell } from "../model/cells";
import {
  scrollToBottom,
  scrollToTop,
  focusAndScrollCellIntoView,
} from "../model/scrollCellIntoView";
import { arrayMove } from "@dnd-kit/sortable";
import { CellId } from "../model/ids";
import { prepareCellForExecution, transitionCell } from "./cell";

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

export type CellAction =
  | {
      type: "SET_CELLS";
      cells: CellState[];
    }
  | {
      type: "CREATE_CELL";
      cellKey: CellId;
      before: boolean;
    }
  | {
      type: "MOVE_CELL";
      cellKey: CellId;
      before: boolean;
    }
  | {
      type: "DROP_CELL_OVER";
      cellKey: CellId;
      overCellKey: CellId;
    }
  | {
      type: "FOCUS_CELL";
      cellKey: CellId;
      before: boolean;
    }
  | {
      type: "FOCUS_TOP_CELL";
    }
  | {
      type: "FOCUS_BOTTOM_CELL";
    }
  | {
      type: "SEND_TO_TOP";
      cellKey: CellId;
    }
  | {
      type: "SEND_TO_BOTTOM";
      cellKey: CellId;
    }
  | {
      type: "MOVE_TO_NEXT_CELL";
      cellKey: CellId;
      before: boolean;
    }
  | {
      type: "DELETE_CELL";
      cellKey: CellId;
    }
  | {
      type: "SCROLL_TO_TARGET";
    }
  | {
      type: "UNDO_DELETE_CELL";
    }
  | {
      type: "HANDLE_CELL_MESSAGE";
      cellKey: CellId;
      message: CellMessage;
    }
  | {
      type: "UPDATE_CELL_CODE";
      cellKey: CellId;
      code: string;
      /**
       * Whether or not the update is a formatting change,
       * if so, the 'edited' state will be handled differently.
       */
      formattingChange: boolean;
    }
  | {
      type: "PREPARE_FOR_RUN";
      cellKey: CellId;
    }
  | {
      type: "FOLD_ALL";
    }
  | {
      type: "UNFOLD_ALL";
    };

function reducer(state: CellsAndHistory, action: CellAction): CellsAndHistory {
  switch (action.type) {
    case "CREATE_CELL": {
      const { cellKey, before } = action;
      const index = state.present.findIndex((cell) => cell.key === cellKey);
      const insertionIndex = before ? index : index + 1;
      const cell = createCell({ key: CellId.create() });

      return {
        ...state,
        present: [
          ...state.present.slice(0, insertionIndex),
          cell,
          ...state.present.slice(insertionIndex),
        ],
      };
    }
    case "MOVE_CELL": {
      const { cellKey, before } = action;
      const index = state.present.findIndex((cell) => cell.key === cellKey);
      const cell = state.present[index];
      if (before && index === 0) {
        return {
          ...state,
          present: [cell, ...state.present.slice(1)],
          scrollKey: cellKey,
        };
      } else if (!before && index === state.present.length - 1) {
        return {
          ...state,
          present: [...state.present.slice(0, -1), cell],
          scrollKey: cellKey,
        };
      }

      return before
        ? {
            ...state,
            present: [
              ...state.present.slice(0, index - 1),
              cell,
              state.present[index - 1],
              ...state.present.slice(index + 1),
            ],
            scrollKey: cellKey,
          }
        : {
            ...state,
            present: [
              ...state.present.slice(0, index),
              state.present[index + 1],
              cell,
              ...state.present.slice(index + 2),
            ],
            scrollKey: cellKey,
          };
    }
    case "DROP_CELL_OVER": {
      const { cellKey, overCellKey } = action;
      const fromIndex = state.present.findIndex((cell) => cell.key === cellKey);
      const toIndex = state.present.findIndex(
        (cell) => cell.key === overCellKey
      );
      return {
        ...state,
        present: arrayMove(state.present, fromIndex, toIndex),
        scrollKey: null,
      };
    }

    case "FOCUS_CELL": {
      if (state.present.length === 0) {
        return state;
      }

      const { cellKey, before } = action;
      const index = state.present.findIndex((cell) => cell.key === cellKey);
      let focusIndex = before ? index - 1 : index + 1;
      // clamp
      focusIndex = Math.max(0, Math.min(focusIndex, state.present.length - 1));
      // can scroll immediately, without setting scrollKey in state, because
      // CellArray won't need to re-render
      focusAndScrollCellIntoView(state.present[focusIndex]);
      return state;
    }
    case "FOCUS_TOP_CELL":
      if (state.present.length === 0) {
        return state;
      }

      state.present[0].ref.current?.editorView.focus();
      scrollToTop();
      return state;

    case "FOCUS_BOTTOM_CELL":
      if (state.present.length === 0) {
        return state;
      }

      state.present[state.present.length - 1].ref.current?.editorView.focus();
      scrollToBottom();
      return state;

    case "SEND_TO_TOP": {
      if (state.present.length === 0) {
        return state;
      }

      const { cellKey } = action;
      const index = state.present.findIndex((cell) => cell.key === cellKey);
      return {
        ...state,
        present: [
          state.present[index],
          ...state.present.slice(0, index),
          ...state.present.slice(index + 1),
        ],
        scrollKey: cellKey,
      };
    }
    case "SEND_TO_BOTTOM": {
      if (state.present.length === 0) {
        return state;
      }

      const { cellKey } = action;
      const index = state.present.findIndex((cell) => cell.key === cellKey);
      return {
        ...state,
        present: [
          ...state.present.slice(0, index),
          ...state.present.slice(index + 1),
          state.present[index],
        ],
        scrollKey: cellKey,
      };
    }
    case "DELETE_CELL": {
      const cellKey = action.cellKey;
      if (state.present.length === 1) {
        return state;
      }

      const index = state.present.findIndex((cell) => cell.key === cellKey);
      const focusIndex = index === 0 ? 1 : index - 1;
      const scrollKey = state.present[focusIndex].key;

      return {
        present: [
          ...state.present.slice(0, index),
          ...state.present.slice(index + 1),
        ],
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
    }
    case "UNDO_DELETE_CELL":
      if (state.history.length === 0) {
        return state;
      } else {
        const mostRecentlyDeleted = state.history[state.history.length - 1];

        const name = mostRecentlyDeleted[0];
        const serializedEditorState = mostRecentlyDeleted[1] || {
          doc: "",
        };
        const index = mostRecentlyDeleted[2];

        const cells = [
          ...state.present.slice(0, index),
          createCell({
            key: CellId.create(),
            name,
            initialContents: serializedEditorState.doc,
            code: serializedEditorState.doc,
            edited: serializedEditorState.doc.trim().length > 0,
            serializedEditorState,
          }),
          ...state.present.slice(index),
        ];

        return {
          ...state,
          present: cells,
          history: state.history.slice(0, -1),
        };
      }

    case "UPDATE_CELL_CODE": {
      const cellToUpdate = state.present.find(
        (cell) => cell.key === action.cellKey
      );
      if (!cellToUpdate) {
        return state;
      }
      if (cellToUpdate.code === action.code) {
        return state;
      }

      return {
        ...state,
        present: state.present.map((cell) => {
          if (cell.key === action.cellKey) {
            return action.formattingChange
              ? // Formatting-only change means we can re-use the last code run
                // if it was not previously edited. And we don't change the edited state.
                {
                  ...cell,
                  code: action.code,
                  lastCodeRun: cell.edited ? cell.lastCodeRun : action.code,
                }
              : {
                  ...cell,
                  code: action.code,
                  edited: action.code.trim() !== cell.lastCodeRun,
                };
          }
          return cell;
        }),
      };
    }
    case "PREPARE_FOR_RUN": {
      const cellToUpdate = state.present.find(
        (cell) => cell.key === action.cellKey
      );
      if (!cellToUpdate) {
        return state;
      }
      return {
        ...state,
        present: state.present.map((cell) => {
          if (cell.key === action.cellKey) {
            return prepareCellForExecution(cellToUpdate);
          }
          return cell;
        }),
      };
    }
    case "HANDLE_CELL_MESSAGE": {
      const { cellKey, message: body } = action;
      return {
        ...state,
        present: state.present.map((cell) => {
          return cell.key === cellKey ? transitionCell(cell, body) : cell;
        }),
      };
    }
    case "SET_CELLS":
      return {
        ...state,
        present: action.cells,
      };
    /**
     * Move focus to next cell
     *
     * Creates a new cell if the current cell is the last one in the array.
     *
     * If needed, scrolls newly created or focused cell into view.
     *
     * Replicates Shift+Enter functionality of Jupyter
     */
    case "MOVE_TO_NEXT_CELL": {
      const { cellKey, before } = action;
      const index = state.present.findIndex((cell) => cell.key === cellKey);
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
    }
    case "SCROLL_TO_TARGET": {
      // Scroll to the specified cell and clear the scroll key.
      const scrollKey = state.scrollKey;
      if (scrollKey === null) {
        return state;
      } else {
        const index = state.present.findIndex((cell) => cell.key === scrollKey);

        // Special-case scrolling to the end of the page: bug in Chrome where
        // browser fails to scrollIntoView an element at the end of a long page
        if (index === state.present.length - 1) {
          state.present[
            state.present.length - 1
          ].ref.current?.editorView.focus();
          scrollToBottom();
        } else {
          focusAndScrollCellIntoView(state.present[index]);
        }

        return {
          ...state,
          scrollKey: null,
        };
      }
    }
    case "FOLD_ALL":
      state.present.forEach((cell) => {
        cell.ref.current?.foldAll();
      });
      return state;
    case "UNFOLD_ALL":
      state.present.forEach((cell) => {
        cell.ref.current?.unfoldAll();
      });
      return state;
    default:
      return state;
  }
}

const cellsAtom = atom<CellsAndHistory>(initialCellState());

export const useCells = () => useAtomValue(cellsAtom);

/**
 * Use this hook to dispatch cell actions. This hook will not cause a re-render
 * when cells change.
 */
export function useCellActions() {
  const setState = useSetAtom(cellsAtom);

  return useMemo(() => {
    const dispatch = (action: CellAction) => {
      setState((state) => reducer(state, action));
    };

    return {
      updateCellCode: (
        cellKey: CellId,
        code: string,
        formattingChange = false
      ) =>
        dispatch({
          type: "UPDATE_CELL_CODE",
          cellKey,
          code,
          formattingChange,
        }),
      prepareForRun: (cellKey: CellId) => {
        dispatch({ type: "PREPARE_FOR_RUN", cellKey });
      },
      createNewCell: (cellKey: CellId, before: boolean) => {
        dispatch({ type: "CREATE_CELL", cellKey, before });
      },
      deleteCell: (cellKey: CellId) => {
        dispatch({ type: "DELETE_CELL", cellKey });
      },
      undoDeleteCell: () => {
        dispatch({ type: "UNDO_DELETE_CELL" });
      },
      focusCell: (cellKey: CellId, before: boolean) => {
        dispatch({ type: "FOCUS_CELL", cellKey, before });
      },
      moveCell: (cellKey: CellId, before: boolean) => {
        dispatch({ type: "MOVE_CELL", cellKey, before });
      },
      dropCellOver: (cellKey: CellId, overCellKey: CellId) => {
        dispatch({ type: "DROP_CELL_OVER", cellKey, overCellKey });
      },
      /* Move focus to next cell
       *
       * Creates a new cell if the current cell is the last one in the array.
       *
       * If needed, scrolls newly created or focused cell into view.
       *
       * Replicates Shift+Enter functionality of Jupyter
       */
      moveToNextCell: (cellKey: CellId, before: boolean) => {
        dispatch({ type: "MOVE_TO_NEXT_CELL", cellKey, before });
      },
      setCells: (cells: CellState[]) => {
        dispatch({ type: "SET_CELLS", cells });
      },
      handleCellMessage: (cellKey: CellId, message: CellMessage) => {
        dispatch({ type: "HANDLE_CELL_MESSAGE", cellKey, message });
      },
      focusTopCell: () => {
        dispatch({ type: "FOCUS_TOP_CELL" });
      },
      focusBottomCell: () => {
        dispatch({ type: "FOCUS_BOTTOM_CELL" });
      },
      sendToTop: (cellKey: CellId) => {
        dispatch({ type: "SEND_TO_TOP", cellKey });
      },
      sendToBottom: (cellKey: CellId) => {
        dispatch({ type: "SEND_TO_BOTTOM", cellKey });
      },
      scrollToTarget: () => {
        dispatch({ type: "SCROLL_TO_TARGET" });
      },
      foldAll: () => {
        dispatch({ type: "FOLD_ALL" });
      },
      unfoldAll: () => {
        dispatch({ type: "UNFOLD_ALL" });
      },
    };
  }, [setState]);
}

/**
 * This is exported for testing purposes only.
 */
export const exportedForTesting = {
  reducer,
  initialCellState,
};
