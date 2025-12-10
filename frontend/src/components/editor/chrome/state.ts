/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { z } from "zod";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { ZodLocalStorage } from "@/utils/storage/typed";
import type { PanelType } from "./types";

export type DeveloperPanelTabType =
  | "errors"
  | "scratchpad"
  | "tracing"
  | "secrets"
  | "logs"
  | "terminal";

export interface ChromeState {
  selectedPanel: PanelType | undefined;
  isSidebarOpen: boolean;
  isDeveloperPanelOpen: boolean;
  selectedDeveloperPanelTab: DeveloperPanelTabType;
}

const KEY = "marimo:sidebar";
const storage = new ZodLocalStorage<ChromeState>(
  z.object({
    selectedPanel: z
      .string()
      .optional()
      .transform((v) => v as PanelType),
    isSidebarOpen: z.boolean(),
    isDeveloperPanelOpen: z.boolean().optional().default(false),
    selectedDeveloperPanelTab: z
      .string()
      .optional()
      .default("terminal")
      .transform((v) => v as DeveloperPanelTabType),
  }),
  initialState,
);

function initialState(): ChromeState {
  return {
    selectedPanel: "variables", // initial panel
    isSidebarOpen: false,
    isDeveloperPanelOpen: false,
    selectedDeveloperPanelTab: "terminal",
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
    toggleDeveloperPanel: (state) => ({
      ...state,
      isDeveloperPanelOpen: !state.isDeveloperPanelOpen,
    }),
    setIsDeveloperPanelOpen: (state, isOpen: boolean) => ({
      ...state,
      isDeveloperPanelOpen: isOpen,
    }),
    setSelectedDeveloperPanelTab: (state, tab: DeveloperPanelTabType) => ({
      ...state,
      selectedDeveloperPanelTab: tab,
    }),
    openDeveloperPanelTab: (state, tab: DeveloperPanelTabType) => ({
      ...state,
      isDeveloperPanelOpen: true,
      selectedDeveloperPanelTab: tab,
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
