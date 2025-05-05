/* Copyright 2024 Marimo. All rights reserved. */
import { createReducerAndAtoms } from "@/utils/createReducer";
import { atom, useAtomValue } from "jotai";
import type { PanelType } from "./types";
import { ZodLocalStorage } from "@/utils/localStorage";
import { z } from "zod";

export interface ChromeState {
  selectedPanel: PanelType | undefined;
  isSidebarOpen: boolean;
  isTerminalOpen: boolean;
}

const storage = new ZodLocalStorage<ChromeState>(
  "marimo:sidebar",
  z.object({
    selectedPanel: z
      .string()
      .optional()
      .transform((v) => v as PanelType),
    isSidebarOpen: z.boolean(),
    isTerminalOpen: z.boolean(),
  }),
  initialState,
);

function initialState(): ChromeState {
  return {
    selectedPanel: "variables", // initial panel
    isSidebarOpen: false,
    isTerminalOpen: false,
  };
}

const {
  reducer,
  createActions,
  valueAtom: chromeAtom,
  useActions,
} = createReducerAndAtoms(
  () => storage.get(),
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
  },
  [(_prevState, newState) => storage.set(newState)],
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

// Context-aware panel

// unique ID of the owner rendering the context-aware panel
// if null, the panel is not open
export const isContextAwarePanelOpenAtom = atom<string | null>(null);
export const isContextAwarePanelPinnedAtom = atom<boolean>(true);
