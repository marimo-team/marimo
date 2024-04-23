/* Copyright 2024 Marimo. All rights reserved. */
import { createReducerAndAtoms } from "@/utils/createReducer";
import { useAtomValue } from "jotai";
import { PanelType } from "./types";

export interface ChromeState {
  selectedPanel: PanelType | undefined;
  isOpen: boolean;
  panelLocation: "left" | "bottom";
}

function initialState(): ChromeState {
  return {
    selectedPanel: "variables", // initial panel
    isOpen: false,
    panelLocation: "left",
  };
}

const {
  reducer,
  createActions,
  valueAtom: chromeAtom,
  useActions,
} = createReducerAndAtoms(initialState, {
  openApplication: (state, selectedPanel: PanelType) => ({
    ...state,
    selectedPanel,
    // If it was closed, open it
    // If it was open, keep it open unless it was the same application
    isOpen: state.isOpen ? state.selectedPanel !== selectedPanel : true,
  }),
  openPanel: (state) => ({ ...state, isOpen: true }),
  closePanel: (state) => ({ ...state, isOpen: false }),
  togglePanel: (state) => ({ ...state, isOpen: !state.isOpen }),
  setIsOpen: (state, isOpen: boolean) => ({ ...state, isOpen }),
  changePanelLocation: (state, panelLocation: "left" | "bottom") => ({
    ...state,
    panelLocation,
  }),
});

export const useChromeState = () => {
  const state = useAtomValue(chromeAtom);
  if (state.isOpen) {
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

/**
 * This is exported for testing purposes only.
 */
export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
};
