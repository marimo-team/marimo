/* Copyright 2024 Marimo. All rights reserved. */

import { createReducerAndAtoms } from "@/utils/createReducer";
import type { Variable, VariableName, Variables } from "./types";
import { useAtomValue } from "jotai";

function initialState(): Variables {
  return {};
}

const {
  reducer,
  createActions,
  valueAtom: variablesAtom,
  useActions,
} = createReducerAndAtoms(initialState, {
  setVariables: (state, variables: Variable[]) => {
    // start with empty state, but keep the old state's metadata
    const oldVariables = { ...state };
    const newVariables: Variables = {};
    for (const variable of variables) {
      newVariables[variable.name] = {
        ...oldVariables[variable.name],
        ...variable,
      };
    }
    return newVariables;
  },
  addVariables: (state, variables: Variable[]) => {
    const newVariables = { ...state };
    for (const variable of variables) {
      newVariables[variable.name] = {
        ...newVariables[variable.name],
        ...variable,
      };
    }
    return newVariables;
  },
  setMetadata: (
    state,
    metadata: Array<{ name: VariableName; value?: string; dataType?: string }>,
  ) => {
    const newVariables = { ...state };
    for (const { name, value, dataType } of metadata) {
      if (!newVariables[name]) {
        continue;
      }

      newVariables[name] = {
        ...newVariables[name],
        value,
        dataType: dataType,
      };
    }
    return newVariables;
  },
});

/**
 * React hook to get the variables state.
 */
export const useVariables = () => useAtomValue(variablesAtom);

/**
 * React hook to get the variables actions.
 */
export function useVariablesActions() {
  return useActions();
}

export { variablesAtom };

export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
};
