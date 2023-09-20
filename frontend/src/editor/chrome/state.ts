/* Copyright 2023 Marimo. All rights reserved. */
import { createReducer } from "@/utils/createReducer";
import { atom, useAtomValue, useSetAtom } from "jotai";
import { useMemo } from "react";
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

const { reducer, createActions } = createReducer(initialState, {
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

const chromeAtom = atom<ChromeState>(initialState());
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
  const setState = useSetAtom(chromeAtom);

  return useMemo(() => {
    const actions = createActions((action) => {
      setState((state) => reducer(state, action));
    });
    return actions;
  }, [setState]);
}

/**
 * This is exported for testing purposes only.
 */
export const exportedForTesting = {
  reducer,
  createActions,
  initialState,
};
