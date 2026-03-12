/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { z } from "zod";
import { store } from "@/core/state/jotai";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { adaptForLocalStorage } from "@/utils/storage/jotai";
import { ZodLocalStorage } from "@/utils/storage/typed";
import type { PanelSection, PanelType } from "./types";
import { PANELS } from "./types";

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
    (p) => !p.hidden && p.defaultSection === "sidebar",
  ).map((p) => p.type),
  developerPanel: PANELS.filter(
    (p) => !p.hidden && p.defaultSection === "developer-panel",
  ).map((p) => p.type),
};

/**
 * Merge saved layout with current defaults so new panels added in later
 * versions are appended to their default section. Panels the user has
 * moved between sections are left where the user put them.
 */
function mergePanelLayout(saved: PanelLayout): PanelLayout {
  const allSaved = new Set([...saved.sidebar, ...saved.developerPanel]);
  return {
    sidebar: [
      ...saved.sidebar,
      ...DEFAULT_PANEL_LAYOUT.sidebar.filter((p) => !allSaved.has(p)),
    ],
    developerPanel: [
      ...saved.developerPanel,
      ...DEFAULT_PANEL_LAYOUT.developerPanel.filter((p) => !allSaved.has(p)),
    ],
  };
}

const panelLayoutStorage = adaptForLocalStorage<PanelLayout, PanelLayout>({
  toSerializable: (v) => v,
  fromSerializable: (saved) => mergePanelLayout(saved),
});

export const panelLayoutAtom = atomWithStorage<PanelLayout>(
  "marimo:panel-layout",
  DEFAULT_PANEL_LAYOUT,
  panelLayoutStorage,
  { getOnInit: true },
);

/**
 * Resolve which section a panel belongs to based on current layout.
 */
function resolvePanelLocation(panelType: PanelType): PanelSection | null {
  const layout = store.get(panelLayoutAtom);
  if (layout.sidebar.includes(panelType)) {
    return "sidebar";
  }
  if (layout.developerPanel.includes(panelType)) {
    return "developer-panel";
  }
  return null;
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
      .default("errors")
      .transform((v) => v as PanelType),
  }),
  initialState,
);

function initialState(): ChromeState {
  return {
    selectedPanel: "variables", // initial panel
    isSidebarOpen: false,
    isDeveloperPanelOpen: false,
    selectedDeveloperPanelTab: "errors",
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
    openApplication: (state, selectedPanel: PanelType) => {
      const location = resolvePanelLocation(selectedPanel);
      if (location === "sidebar") {
        return {
          ...state,
          selectedPanel,
          isSidebarOpen: true,
        };
      }
      if (location === "developer-panel") {
        return {
          ...state,
          selectedDeveloperPanelTab: selectedPanel,
          isDeveloperPanelOpen: true,
        };
      }
      // Panel not found in layout, no-op
      return state;
    },
    toggleApplication: (state, selectedPanel: PanelType) => {
      const location = resolvePanelLocation(selectedPanel);
      if (location === "sidebar") {
        return {
          ...state,
          selectedPanel,
          // If it was closed, open it
          // If it was open, keep it open unless it was the same application
          isSidebarOpen: state.isSidebarOpen
            ? state.selectedPanel !== selectedPanel
            : true,
        };
      }
      if (location === "developer-panel") {
        return {
          ...state,
          selectedDeveloperPanelTab: selectedPanel,
          // If it was closed, open it
          // If it was open, keep it open unless it was the same tab
          isDeveloperPanelOpen: state.isDeveloperPanelOpen
            ? state.selectedDeveloperPanelTab !== selectedPanel
            : true,
        };
      }
      // Panel not found in layout, no-op
      return state;
    },
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
  mergePanelLayout,
};
