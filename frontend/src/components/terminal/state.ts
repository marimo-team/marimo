/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { generateUUID } from "@/utils/uuid";

export interface TerminalCommand {
  id: string;
  text: string;
  timestamp: number;
}

export interface TerminalState {
  pendingCommands: TerminalCommand[];
  isReady: boolean;
}

function initialState(): TerminalState {
  return {
    pendingCommands: [],
    isReady: false,
  };
}

const {
  reducer,
  createActions,
  valueAtom: terminalStateAtom,
  useActions,
} = createReducerAndAtoms(initialState, {
  addCommand: (state, text: string) => {
    const command: TerminalCommand = {
      id: generateUUID(),
      text,
      timestamp: Date.now(),
    };

    return {
      ...state,
      pendingCommands: [...state.pendingCommands, command],
    };
  },
  removeCommand: (state, commandId: string) => ({
    ...state,
    pendingCommands: state.pendingCommands.filter(
      (cmd) => cmd.id !== commandId,
    ),
  }),
  setReady: (state, isReady: boolean) => ({
    ...state,
    isReady,
  }),
  clearCommands: (state) => ({
    ...state,
    pendingCommands: [],
  }),
});

/**
 * React hook to get the terminal state.
 */
export const useTerminalState = () => useAtomValue(terminalStateAtom);

/**
 * React hook to get the terminal actions.
 */
export function useTerminalActions() {
  return useActions();
}

export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
};
