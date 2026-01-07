/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { z } from "zod";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { jotaiJsonStorage } from "@/utils/storage/jotai";
import { ZodLocalStorage } from "@/utils/storage/typed";
import type { PanelType } from "./types";
import { isPanelHidden, PANELS } from "./types";

export interface ChromeState {
  selectedPanel: PanelType | undefined;
  isSidebarOpen: boolean;
  isDeveloperPanelOpen: boolean;
  selectedDeveloperPanelTab: PanelType;
}

/**
 * Layout configuration for panels in sidebar and developer panel.
 * Each array contains the ordered list of visible panel IDs for that section.
 */
export interface PanelLayout {
  sidebar: PanelType[];
  developerPanel: PanelType[];
}

const DEFAULT_PANEL_LAYOUT: PanelLayout = {
  sidebar: PANELS.filter(
    (p) => !isPanelHidden(p) && p.defaultSection === "sidebar",
  ).map((p) => p.type),
  developerPanel: PANELS.filter(
    (p) => !isPanelHidden(p) && p.defaultSection === "developer-panel",
  ).map((p) => p.type),
};

export const panelLayoutAtom = atomWithStorage<PanelLayout>(
  "marimo:panel-layout",
  DEFAULT_PANEL_LAYOUT,
  jotaiJsonStorage,
  { getOnInit: true },
);

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
      .transform((v) => v as PanelType),
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
    setSelectedDeveloperPanelTab: (state, tab: PanelType) => ({
      ...state,
      selectedDeveloperPanelTab: tab,
    }),
    openDeveloperPanelTab: (state, tab: PanelType) => ({
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
