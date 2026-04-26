/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import {
  getCellRendererPlugin,
  type LayoutDataByType,
} from "@/components/editor/renderers/plugins";
import type { LayoutType } from "@/components/editor/renderers/types";
import { logNever } from "@/utils/assertNever";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { getNotebook } from "../cells/cells";
import { notebookCells } from "../cells/utils";
import { store } from "../state/jotai";

export type LayoutData = LayoutDataByType[LayoutType];
export type SetLayoutDataPayload = {
  [K in LayoutType]: { layoutView: K; data: LayoutDataByType[K] };
}[LayoutType];

export interface LayoutState {
  selectedLayout: LayoutType;
  layoutData: Partial<LayoutDataByType>;
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
    setLayoutData: (state, payload: SetLayoutDataPayload) => {
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
    return null;
  }
  const cells = notebookCells(notebook);

  // Fall back to the plugin's initial layout when the user has not yet
  // interacted with this layout — otherwise serializers that expect a
  // structured layout object crash on `undefined`.
  const serialize = <K extends LayoutType>(type: K) => {
    const plugin = getCellRendererPlugin(type);
    const data = layoutData[type] ?? plugin.getInitialLayout(cells);
    return { type, data: plugin.serializeLayout(data, cells) };
  };

  switch (selectedLayout) {
    case "grid":
      return serialize("grid");
    case "slides":
      return serialize("slides");
    default:
      logNever(selectedLayout);
      return null;
  }
}
