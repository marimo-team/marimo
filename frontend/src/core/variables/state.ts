/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { createReducerAndAtoms } from "@/utils/createReducer";
import type { Variable, VariableName, Variables } from "./types";

function initialState(): Variables {
  return {};
}

/**
 * Check if two variables are equal
 */
function areVariablesEqual(a: Variable, b: Variable): boolean {
  return (
    a.name === b.name &&
    JSON.stringify(a.declaredBy) === JSON.stringify(b.declaredBy) &&
    JSON.stringify(a.usedBy) === JSON.stringify(b.usedBy) &&
    a.value === b.value &&
    a.dataType === b.dataType
  );
}

const {
  reducer,
  createActions,
  valueAtom: variablesAtom,
  useActions,
} = createReducerAndAtoms(initialState, {
  setVariables: (state, variables: Variable[]) => {
    // If setting to empty, only clear if state has variables
    if (variables.length === 0) {
      if (Object.keys(state).length === 0) {
        return state; // Already empty, no-op
      }
      return {}; // Clear the state
    }

    // start with empty state, but keep the old state's metadata
    const oldVariables = { ...state };
    const newVariables: Variables = {};
    let hasChanges = false;

    for (const variable of variables) {
      const mergedVariable = {
        ...oldVariables[variable.name],
        ...variable,
      };
      newVariables[variable.name] = mergedVariable;

      // Check if this variable actually changed
      if (!hasChanges && oldVariables[variable.name]) {
        if (!areVariablesEqual(oldVariables[variable.name], mergedVariable)) {
          hasChanges = true;
        }
      } else if (!hasChanges) {
        // New variable added
        hasChanges = true;
      }
    }

    // Check if any variables were removed
    if (!hasChanges) {
      const oldKeys = Object.keys(state);
      const newKeys = Object.keys(newVariables);
      if (oldKeys.length !== newKeys.length) {
        hasChanges = true;
      }
    }

    // Return old state if nothing changed
    if (
      !hasChanges &&
      Object.keys(state).length === Object.keys(newVariables).length
    ) {
      return state;
    }

    return newVariables;
  },
  addVariables: (state, variables: Variable[]) => {
    // No-op if empty
    if (variables.length === 0) {
      return state;
    }

    const newVariables = { ...state };
    let hasChanges = false;

    for (const variable of variables) {
      const existingVariable = newVariables[variable.name];
      const mergedVariable = {
        ...existingVariable,
        ...variable,
      };

      // Check if this variable actually changed
      if (!hasChanges) {
        if (
          !existingVariable ||
          !areVariablesEqual(existingVariable, mergedVariable)
        ) {
          hasChanges = true;
        }
      }

      newVariables[variable.name] = mergedVariable;
    }

    // Return old state if nothing changed
    if (!hasChanges) {
      return state;
    }

    return newVariables;
  },
  setMetadata: (
    state,
    metadata: {
      name: VariableName;
      value?: string | null;
      dataType?: string | null;
    }[],
  ) => {
    // No-op if empty
    if (metadata.length === 0) {
      return state;
    }

    const newVariables = { ...state };
    let hasChanges = false;

    for (const { name, value, dataType } of metadata) {
      if (!newVariables[name]) {
        continue;
      }

      const existingVariable = newVariables[name];
      // Check if metadata actually changed
      if (
        !hasChanges &&
        (existingVariable.value !== value ||
          existingVariable.dataType !== dataType)
      ) {
        hasChanges = true;
      }

      newVariables[name] = {
        ...existingVariable,
        value,
        dataType: dataType,
      };
    }

    // Return old state if nothing changed
    if (!hasChanges) {
      return state;
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
