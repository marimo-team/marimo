/* Copyright 2024 Marimo. All rights reserved. */
import { createReducerAndAtoms } from "@/utils/createReducer";
import { useAtomValue } from "jotai";
import type { PanelType } from "./types";
import { ZodLocalStorage } from "@/utils/localStorage";
import { z } from "zod";
import { PANELS } from "./types";

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
    nextPanel: (state) => {
      if (!state.isSidebarOpen || !state.selectedPanel) {
        return state;
      }
      const visiblePanels = PANELS.filter(
        (p) => !p.hidden && p.position === "sidebar",
      );
      const currentIndex = visiblePanels.findIndex(
        (p) => p.type === state.selectedPanel,
      );
      const nextIndex = (currentIndex + 1) % visiblePanels.length;
      return {
        ...state,
        selectedPanel: visiblePanels[nextIndex].type,
      };
    },
    previousPanel: (state) => {
      if (!state.isSidebarOpen || !state.selectedPanel) {
        return state;
      }
      const visiblePanels = PANELS.filter(
        (p) => !p.hidden && p.position === "sidebar",
      );
      const currentIndex = visiblePanels.findIndex(
        (p) => p.type === state.selectedPanel,
      );
      const prevIndex =
        (currentIndex - 1 + visiblePanels.length) % visiblePanels.length;
      return {
        ...state,
        selectedPanel: visiblePanels[prevIndex].type,
      };
    },
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
