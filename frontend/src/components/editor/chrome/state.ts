/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { z } from "zod";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { ZodLocalStorage } from "@/utils/localStorage";
import type { PanelType } from "./types";

export interface ChromeState {
  selectedPanel: PanelType | undefined;
  isSidebarOpen: boolean;
  isTerminalOpen: boolean;
  isMinimapOpen: boolean;
}

const KEY = "marimo:sidebar";
const storage = new ZodLocalStorage<ChromeState>(
  z.object({
    selectedPanel: z
      .string()
      .optional()
      .transform((v) => v as PanelType),
    isSidebarOpen: z.boolean(),
    isTerminalOpen: z.boolean(),
    isMinimapOpen: z.boolean(),
  }),
  initialState,
);

function initialState(): ChromeState {
  return {
    selectedPanel: "variables", // initial panel
    isSidebarOpen: false,
    isTerminalOpen: false,
    isMinimapOpen: false,
  };
}

const {
  reducer,
  createActions,
  valueAtom: chromeAtom,
  useActions,
} = createReducerAndAtoms(
  () => storage.get(KEY),
  {
    openApplication: (state, selectedPanel: PanelType) => ({
      ...state,
      selectedPanel,
      isSidebarOpen: true,
    }),
    toggleApplication: (state, selectedPanel: PanelType) => ({
      ...state,
      selectedPanel,
      // If it was closed, open it
      // If it was open, keep it open unless it was the same application
      isSidebarOpen: state.isSidebarOpen
        ? state.selectedPanel !== selectedPanel
        : true,
    }),
    toggleSidebarPanel: (state) => ({
      ...state,
      isSidebarOpen: !state.isSidebarOpen,
    }),
    setIsSidebarOpen: (state, isOpen: boolean) => ({
      ...state,
      isSidebarOpen: isOpen,
    }),
    toggleTerminal: (state) => ({
      ...state,
      isTerminalOpen: !state.isTerminalOpen,
    }),
    setIsTerminalOpen: (state, isOpen: boolean) => ({
      ...state,
      isTerminalOpen: isOpen,
    }),
    toggleMinimap: (state) => ({
      ...state,
      isMinimapOpen: !state.isMinimapOpen,
    }),
    setIsMinimapOpen: (state, isOpen: boolean) => ({
      ...state,
      isMinimapOpen: isOpen,
    }),
  },
  [(_prevState, newState) => storage.set(KEY, newState)],
);

export const useChromeState = () => {
  const state = useAtomValue(chromeAtom);
  if (state.isSidebarOpen) {
    return state;
  }
  return {
    ...state,
    selectedPanel: undefined,
  };
};

export function useChromeActions() {
  return useActions();
}

export { chromeAtom };

/**
 * This is exported for testing purposes only.
 */
export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
};
