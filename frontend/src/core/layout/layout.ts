/* Copyright 2024 Marimo. All rights reserved. */
import { GridLayout } from "@/components/editor/renderers/grid-layout/types";
import { LayoutType } from "@/components/editor/renderers/types";
import { atom, useAtomValue, useSetAtom } from "jotai";
import { createReducer } from "@/utils/createReducer";
import { useMemo } from "react";
import { cellRendererPlugins } from "@/components/editor/renderers/plugins";
import { getNotebook, notebookCells } from "../cells/cells";
import { store } from "../state/jotai";
import { Logger } from "@/utils/Logger";

export type LayoutData = GridLayout | undefined;

export interface LayoutState {
  selectedLayout: LayoutType;
  layoutData: Partial<Record<LayoutType, LayoutData>>;
}

export function initialLayoutState(): LayoutState {
  return {
    selectedLayout: "vertical",
    layoutData: {},
  };
}

const { reducer, createActions } = createReducer(initialLayoutState, {
  setLayoutView: (state, payload: LayoutType) => {
    return {
      ...state,
      selectedLayout: payload,
    };
  },
  setLayoutData: (
    state,
    payload: { layoutView: LayoutType; data: LayoutData },
  ) => {
    return {
      ...state,
      selectedLayout: payload.layoutView,
      layoutData: {
        ...state.layoutData,
        [payload.layoutView]: payload.data,
      },
    };
  },
  setCurrentLayoutData: (state, payload: LayoutData) => {
    return {
      ...state,
      layoutData: {
        ...state.layoutData,
        [state.selectedLayout]: payload,
      },
    };
  },
});

const layoutStateAtom = atom<LayoutState>(initialLayoutState());

export const useLayoutState = () => {
  return useAtomValue(layoutStateAtom);
};

export const useLayoutActions = () => {
  const setState = useSetAtom(layoutStateAtom);

  return useMemo(() => {
    const actions = createActions((action) => {
      setState((state) => reducer(state, action));
    });
    return actions;
  }, [setState]);
};

/**
 * Get the serialized layout data, to be used when saving.
 */
export function getSerializedLayout() {
  const notebook = getNotebook();
  const { layoutData, selectedLayout } = store.get(layoutStateAtom);

  // Vertical layout has no data, as it is the default.
  if (selectedLayout === "vertical") {
    return undefined;
  }

  if (layoutData === undefined) {
    return undefined;
  }

  const data = layoutData[selectedLayout];
  const plugin = cellRendererPlugins.find(
    (plugin) => plugin.type === selectedLayout,
  );
  if (plugin === undefined) {
    Logger.error(`Unknown layout type: ${selectedLayout}`);
    return undefined;
  }
  return {
    type: selectedLayout,
    data: plugin.serializeLayout(data, notebookCells(notebook)),
  };
}
