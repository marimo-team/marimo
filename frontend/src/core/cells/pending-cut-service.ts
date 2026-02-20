/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import type { ClipboardCellData } from "@/components/editor/navigation/clipboard";
import type { CellId } from "@/core/cells/ids";
import { store } from "@/core/state/jotai";
import { createReducerAndAtoms } from "@/utils/createReducer";

interface PendingCutState {
  cellIds: Set<CellId>;
  clipboardData: ClipboardCellData | null;
}

const initialState = (): PendingCutState => ({
  cellIds: new Set(),
  clipboardData: null,
});

const {
  valueAtom: pendingCutStateAtom,
  useActions: usePendingCutActionsInternal,
} = createReducerAndAtoms(initialState, {
  markForCut: (
    _state,
    action: { cellIds: CellId[]; clipboardData: ClipboardCellData },
  ) => {
    return {
      cellIds: new Set(action.cellIds),
      clipboardData: action.clipboardData,
    };
  },
  clear: () => {
    return initialState();
  },
});

// Re-export the state atom
export { pendingCutStateAtom };

// Derived atom just for cell IDs (for easier consumption)
export const pendingCutCellIdsAtom = atom(
  (get) => get(pendingCutStateAtom).cellIds,
);

export const clearPendingCutAtom = atom(null, () => {
  store.set(pendingCutStateAtom, initialState());
});

export function usePendingCutActions() {
  return usePendingCutActionsInternal();
}

export function useIsPendingCut(cellId: CellId): boolean {
  const cellIds = useAtomValue(pendingCutCellIdsAtom);
  return cellIds.has(cellId);
}

export function usePendingCutState() {
  return useAtomValue(pendingCutStateAtom);
}

export function useHasPendingCut(): boolean {
  const state = useAtomValue(pendingCutStateAtom);
  return state.cellIds.size > 0;
}
