/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import type { GridLayout } from "@/components/editor/renderers/grid-layout/types";
import type { SlidesLayout } from "@/components/editor/renderers/slides-layout/types";
import {
  type LayoutType,
  isLayoutType,
  OVERRIDABLE_LAYOUT_TYPES,
} from "@/components/editor/renderers/types";
import { KnownQueryParams } from "@/core/constants";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { isRecord } from "@/utils/records";

export type LayoutData = GridLayout | SlidesLayout | null | undefined;

export interface SerializedLayout {
  type: string;
  data: unknown;
}

export function isSerializedLayout(value: unknown): value is SerializedLayout {
  return isRecord(value) && typeof value.type === "string" && "data" in value;
}

interface LayoutStateBase {
  selectedLayout: LayoutType;
  layoutData: Partial<Record<LayoutType, LayoutData>>;
}

export type LayoutState =
  | (LayoutStateBase & { pendingLayout: SerializedLayout })
  | (LayoutStateBase & { pendingLayout?: never });

export function initialLayoutState(
  serializedLayout?: SerializedLayout,
): LayoutState {
  if (serializedLayout && isLayoutType(serializedLayout.type)) {
    return {
      selectedLayout: serializedLayout.type,
      layoutData: {},
      pendingLayout: serializedLayout,
    };
  }
  return {
    selectedLayout: "vertical",
    layoutData: {},
  };
}

export function selectLayout(
  state: LayoutState,
  selectedLayout: LayoutType,
): LayoutState {
  if (selectedLayout === state.selectedLayout) {
    return state;
  }
  const { pendingLayout: _pendingLayout, ...materializedState } = state;
  return { ...materializedState, selectedLayout };
}

const { valueAtom: layoutStateAtom, useActions } = createReducerAndAtoms(
  initialLayoutState,
  {
    setLayoutView: selectLayout,
    setLayoutData: (
      { pendingLayout: _pendingLayout, ...state },
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
    setCurrentLayoutData: (
      { pendingLayout: _pendingLayout, ...state },
      payload: LayoutData,
    ) => {
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

export function resolveLayoutType({
  selectedLayout,
  isReading,
  searchParams,
}: {
  selectedLayout: LayoutType;
  isReading: boolean;
  searchParams: URLSearchParams;
}): LayoutType {
  if (!isReading) {
    return selectedLayout;
  }
  const requested = searchParams.get(KnownQueryParams.viewAs);
  return (
    OVERRIDABLE_LAYOUT_TYPES.find((layout) => layout === requested) ??
    selectedLayout
  );
}
