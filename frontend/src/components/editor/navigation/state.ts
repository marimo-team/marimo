/* Copyright 2024 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { useMemo } from "react";
import type { CellId } from "@/core/cells/ids";
import { createReducerAndAtoms } from "@/utils/createReducer";

type TemporarilyShownCodeState = Set<CellId>;

// This previously used jotai-scope, but unfortunately this bug creates unnecessary work:
// https://github.com/jotaijs/jotai-scope/issues/25

const {
  valueAtom: temporarilyShownCodeAtom,
  useActions: useTemporarilyShownCodeActions,
} = createReducerAndAtoms(() => new Set<CellId>(), {
  add: (state: TemporarilyShownCodeState, cellId: CellId) => {
    const newState = new Set(state);
    newState.add(cellId);
    return newState;
  },
  remove: (state: TemporarilyShownCodeState, cellId: CellId) => {
    const newState = new Set(state);
    newState.delete(cellId);
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
