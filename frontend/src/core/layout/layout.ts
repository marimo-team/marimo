/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import type { GridLayout } from "@/components/editor/renderers/grid-layout/types";
import { cellRendererPlugins } from "@/components/editor/renderers/plugins";
import type { LayoutType } from "@/components/editor/renderers/types";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { Logger } from "@/utils/Logger";
import { getNotebook } from "../cells/cells";
import { notebookCells } from "../cells/utils";
import { store } from "../state/jotai";

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

const { valueAtom: layoutStateAtom, useActions } = createReducerAndAtoms(
  initialLayoutState,
  {
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
  },
);

export { layoutStateAtom };

export const useLayoutState = () => {
  return useAtomValue(layoutStateAtom);
};

export const useLayoutActions = () => {
  return useActions();
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
