/* Copyright 2023 Marimo. All rights reserved. */

import { createReducer } from "@/utils/createReducer";
import { Variables } from "./types";
import { atom, useAtomValue, useSetAtom } from "jotai";
import { useMemo } from "react";

function initialState(): Variables {
  return {};
}

const { reducer, createActions } = createReducer(initialState, {
  setVariables: (_state, variables: Variables) => {
    return variables;
  },
  addVariables: (state, variables: Variables) => {
    return { ...state, ...variables };
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
