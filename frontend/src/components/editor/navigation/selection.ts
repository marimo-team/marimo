/* Copyright 2026 Marimo. All rights reserved. */
import { atom, type createStore, useAtomValue } from "jotai";
import { useMemo } from "react";
import type { CellId } from "@/core/cells/ids";
import type { Layout } from "@/core/cells/layout";
import { createReducerAndAtoms } from "@/utils/createReducer";

export interface CellSelectionState {
  selectionStart: CellId | null;
  selectionEnd: CellId | null;
  selected: Set<CellId>;
}

function initialState(): CellSelectionState {
  return {
    selectionStart: null,
    selectionEnd: null,
    selected: new Set(),
  };
}

const {
  reducer,
  createActions,
  valueAtom: cellSelectionAtom,
  useActions,
} = createReducerAndAtoms(initialState, {
  select: (
    _state: CellSelectionState,
    payload: { cellId: CellId },
  ): CellSelectionState => ({
    selectionStart: payload.cellId,
    selectionEnd: payload.cellId,
    selected: new Set([payload.cellId]),
  }),

  /**
   * Extend the selection from where it started to `cellId`, over the cells
   * the page shows between them. Cells a fold hides are stepped over, as
   * the focus steps over them.
   */
  extend: (
    state: CellSelectionState,
    payload: { cellId: CellId; layout: Layout },
  ): CellSelectionState => {
    const { cellId, layout } = payload;
    const start = state.selectionStart;
    const column =
      start === null
        ? undefined
        : layout.columns.find((column) => column.visible.includes(start));
    const startIdx =
      start === null ? -1 : (column?.visible.indexOf(start) ?? -1);
    const endIdx = column?.visible.indexOf(cellId) ?? -1;
    if (
      start === null ||
      column === undefined ||
      startIdx === -1 ||
      endIdx === -1
    ) {
      // Nothing to extend from, or the cells are not on the page together.
      return {
        selectionStart: cellId,
        selectionEnd: cellId,
        selected: new Set([cellId]),
      };
    }
    const [from, to] =
      startIdx < endIdx ? [startIdx, endIdx] : [endIdx, startIdx];
    return {
      selectionStart: start,
      selectionEnd: cellId,
      selected: new Set(column.visible.slice(from, to + 1)),
    };
  },

  clear: (state: CellSelectionState): CellSelectionState => {
    if (state.selected.size === 0) {
      // Already cleared
      return state;
    }
    return initialState();
  },
});

/**
 * React hook to get the cell selection state.
 */
export const useCellSelectionState = () => useAtomValue(cellSelectionAtom);

export function useIsCellSelected(cellId: CellId) {
  const cellSelectedAtom = useMemo(
    () => atom((get) => get(cellSelectionAtom).selected.has(cellId)),
    [cellId],
  );
  return useAtomValue(cellSelectedAtom);
}

/**
 * React hook to get the cell selection actions.
 */
export function useCellSelectionActions() {
  return useActions();
}

export function getSelectedCells(store: ReturnType<typeof createStore>) {
  return store.get(cellSelectionAtom).selected;
}

export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
  cellSelectionAtom,
};
