/* Copyright 2024 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { useMemo } from "react";
import { type CellId, HTMLCellId } from "@/core/cells/ids";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { raf2, scrollCellIntoView } from "./focus-utils";

type TemporarilyShownCodeState = Set<CellId>;

// This previously used jotai-scope, but unfortunately this bug creates unnecessary work:
// https://github.com/jotaijs/jotai-scope/issues/25

const {
  valueAtom: temporarilyShownCodeAtom,
  useActions: useTemporarilyShownCodeActions,
} = createReducerAndAtoms(() => new Set<CellId>(), {
  add: (state: TemporarilyShownCodeState, cellId: CellId) => {
    if (state.has(cellId)) {
      // no-op
      return state;
    }
    const newState = new Set(state);
    newState.add(cellId);
    return newState;
  },
  remove: (state: TemporarilyShownCodeState, cellId: CellId) => {
    if (!state.has(cellId)) {
      // no-op
      return state;
    }
    const newState = new Set(state);
    newState.delete(cellId);

    // If we are hiding the code, this will cause a layout shift
    // so we need to scroll cursor/activeElement into view.
    raf2(() => {
      // Get the active
      const activeElement = document.activeElement;
      if (!activeElement) {
        return;
      }
      // Get the current focused cell id
      const focusedCell =
        HTMLCellId.findElementThroughShadowDOMs(activeElement);
      if (!focusedCell) {
        return;
      }
      scrollCellIntoView(HTMLCellId.parse(focusedCell.id));
    });

    return newState;
  },
});

const createTemporarilyShownCodeAtom = (cellId: CellId) =>
  atom((get) => get(temporarilyShownCodeAtom).has(cellId));

export function useTemporarilyShownCode(cellId: CellId) {
  const atom = useMemo(() => createTemporarilyShownCodeAtom(cellId), [cellId]);
  return useAtomValue(atom);
}

export { temporarilyShownCodeAtom, useTemporarilyShownCodeActions };
