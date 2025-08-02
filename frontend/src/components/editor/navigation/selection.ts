/* Copyright 2024 Marimo. All rights reserved. */
import { atom, type createStore, useAtomValue } from "jotai";
import { useMemo } from "react";
import type { CellId } from "@/core/cells/ids";
import { createReducerAndAtoms } from "@/utils/createReducer";
import type { MultiColumn } from "@/utils/id-tree";

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

  extend: (
    state: CellSelectionState,
    payload: {
      cellId: CellId;
      allCellIds: MultiColumn<CellId>;
    },
  ): CellSelectionState => {
    if (!state.selectionStart) {
      // fallback to single select
      return {
        selectionStart: payload.cellId,
        selectionEnd: payload.cellId,
        selected: new Set([payload.cellId]),
      };
    }
    const { cellId, allCellIds } = payload;

    try {
      const column = allCellIds.findWithId(state.selectionStart);
      const startIdx = column.indexOfOrThrow(state.selectionStart);
      const endIdx = column.indexOfOrThrow(cellId);
      const [from, to] =
        startIdx < endIdx ? [startIdx, endIdx] : [endIdx, startIdx];
      const selected = column.slice(from, to + 1);
      return {
        selectionStart: state.selectionStart,
        selectionEnd: cellId,
        selected: new Set(selected),
      };
    } catch {
      // fallback to single select
      return {
        selectionStart: cellId,
        selectionEnd: cellId,
        selected: new Set([cellId]),
      };
    }
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
