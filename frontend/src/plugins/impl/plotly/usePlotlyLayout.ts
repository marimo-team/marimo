/* Copyright 2026 Marimo. All rights reserved. */

import { usePrevious } from "@uidotdev/usehooks";
import { isEqual, pick } from "lodash-es";
import type * as Plotly from "plotly.js";
import { useEffect, useState } from "react";
import { Objects } from "@/utils/objects";
import type { Figure } from "./Plot";

/**
 * Keys that are preserved across figure updates when set by user interaction.
 * These include dragmode and axis settings that users may adjust.
 */
export const PERSISTED_LAYOUT_KEYS = ["dragmode", "xaxis", "yaxis"] as const;

/**
 * Keys that are omitted from layout updates unless they changed in the figure.
 * This prevents overwriting user interactions like zoom/pan.
 */
export const LAYOUT_OMIT_KEYS: (keyof Plotly.Layout)[] = [
  "autosize",
  "dragmode",
  "xaxis",
  "yaxis",
];

/**
 * Creates the initial layout for a Plotly figure with sensible defaults.
 */
export function createInitialLayout(figure: Figure): Partial<Plotly.Layout> {
  // Enable autosize if width is not specified
  const shouldAutoSize = figure.layout.width === undefined;
  return {
    autosize: shouldAutoSize,
    dragmode: "select",
    height: 540,
    // Prioritize user's config
    ...figure.layout,
  };
}

/**
 * Computes the updated layout when the figure changes.
 * Preserves user-interaction values (dragmode, xaxis, yaxis) while
 * taking everything else from the new figure's layout.
 */
export function computeLayoutOnFigureChange(
  nextFigure: Figure,
  prevLayout: Partial<Plotly.Layout>,
): Partial<Plotly.Layout> {
  return {
    ...createInitialLayout(nextFigure),
    ...pick(prevLayout, PERSISTED_LAYOUT_KEYS),
  };
}

/**
 * Computes which keys to omit from layout updates based on what changed.
 * If a key changed in the figure, we should update it even if it's normally omitted.
 */
export function computeOmitKeys(
  currentLayout: Partial<Plotly.Layout>,
  previousLayout: Partial<Plotly.Layout>,
): Set<keyof Plotly.Layout> {
  const omitKeys = new Set<keyof Plotly.Layout>(LAYOUT_OMIT_KEYS);

  // If the key was updated externally (e.g. can be specifically passed in the config)
  // then we need to update the layout
  for (const key of omitKeys) {
    if (!isEqual(currentLayout[key], previousLayout[key])) {
      omitKeys.delete(key);
    }
  }

  return omitKeys;
}

/**
 * Computes the layout update when figure.layout changes.
 * Omits keys that shouldn't override user interactions unless they changed.
 */
export function computeLayoutUpdate(
  figureLayout: Partial<Plotly.Layout>,
  previousFigureLayout: Partial<Plotly.Layout>,
  prevLayout: Partial<Plotly.Layout>,
): Partial<Plotly.Layout> {
  const omitKeys = computeOmitKeys(figureLayout, previousFigureLayout);
  const layoutUpdate = Objects.omit(figureLayout, omitKeys);
  return { ...prevLayout, ...layoutUpdate };
}

interface UsePlotlyLayoutOptions {
  originalFigure: Figure;
  initialValue?: Partial<Plotly.Layout>;
  isScriptLoaded?: boolean;
}

interface UsePlotlyLayoutResult {
  figure: Figure;
  layout: Partial<Plotly.Layout>;
  setLayout: React.Dispatch<React.SetStateAction<Partial<Plotly.Layout>>>;
  handleReset: () => void;
}

/**
 * Hook that manages the Plotly figure and layout state.
 *
 * This hook handles:
 * - Cloning the figure to prevent Plotly mutations
 * - Managing layout state with proper preservation of user interactions
 * - Syncing layout when the figure changes
 * - Providing a reset function to restore original state
 */
export function usePlotlyLayout({
  originalFigure,
  initialValue,
  isScriptLoaded = true,
}: UsePlotlyLayoutOptions): UsePlotlyLayoutResult {
  const [figure, setFigure] = useState(() => {
    // We clone the figure since Plotly mutates the figure in place
    return structuredClone(originalFigure);
  });

  const [layout, setLayout] = useState<Partial<Plotly.Layout>>(() => {
    return {
      ...createInitialLayout(figure),
      // Override with persisted values (dragmode, xaxis, yaxis)
      ...initialValue,
    };
  });

  // Update figure and layout when originalFigure changes
  useEffect(() => {
    const nextFigure = structuredClone(originalFigure);
    setFigure(nextFigure);
    // Start with the new figure's layout, then only preserve user-interaction
    // values (dragmode, xaxis, yaxis) from the previous layout.
    // We don't want to preserve other properties like `shapes` from the previous
    // layout, as they should be fully controlled by the figure prop.
    setLayout((prev) => computeLayoutOnFigureChange(nextFigure, prev));
  }, [originalFigure, isScriptLoaded]);

  const prevFigure = usePrevious(figure) ?? figure;

  // Sync layout when figure.layout changes
  useEffect(() => {
    setLayout((prev) =>
      computeLayoutUpdate(figure.layout, prevFigure.layout, prev),
    );
  }, [figure.layout, prevFigure.layout]);

  const handleReset = () => {
    const nextFigure = structuredClone(originalFigure);
    setFigure(nextFigure);
    setLayout(createInitialLayout(nextFigure));
  };

  return {
    figure,
    layout,
    setLayout,
    handleReset,
  };
}
