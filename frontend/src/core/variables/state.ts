/* Copyright 2024 Marimo. All rights reserved. */

import { createReducer } from "@/utils/createReducer";
import { Variable, VariableName, Variables } from "./types";
import { atom, useAtomValue, useSetAtom } from "jotai";
import { useMemo } from "react";

function initialState(): Variables {
  return {};
}

const { reducer, createActions } = createReducer(initialState, {
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

const variablesAtom = atom(initialState());

/**
 * React hook to get the variables state.
 */
export const useVariables = () => useAtomValue(variablesAtom);

/**
 * React hook to get the variables actions.
 */
export function useVariablesActions() {
  const setState = useSetAtom(variablesAtom);
  return useMemo(() => {
    const actions = createActions((action) => {
      setState((state) => reducer(state, action));
    });
    return actions;
  }, [setState]);
}

export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
};
