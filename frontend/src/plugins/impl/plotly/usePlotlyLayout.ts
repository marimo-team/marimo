/* Copyright 2026 Marimo. All rights reserved. */

import { usePrevious } from "@uidotdev/usehooks";
import { dequal as isEqual } from "dequal";
import type * as Plotly from "plotly.js";
import { useEffect, useRef, useState } from "react";
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
 * Returns true if two figures have compatible trace types.
 * When traces are incompatible (different types, count, or order), axis settings
 * from the old figure should not be preserved as they would distort the
 * new chart. See https://github.com/marimo-team/marimo/issues/5898
 */
export function hasCompatibleTraces(prev: Figure, next: Figure): boolean {
  if (prev.data.length !== next.data.length) {
    return false;
  }
  return prev.data.every(
    (trace, i) =>
      (trace.type ?? "scatter") === (next.data[i]?.type ?? "scatter"),
  );
}

/**
 * Computes the updated layout when the figure changes.
 * Preserves user-interaction values (dragmode, xaxis, yaxis) while
 * taking everything else from the new figure's layout.
 *
 * When trace types change, only dragmode is preserved — axis settings
 * are reset to let Plotly auto-compute ranges for the new chart type.
 */
export function computeLayoutOnFigureChange(
  nextFigure: Figure,
  prevFigure: Figure,
  prevLayout: Partial<Plotly.Layout>,
): Partial<Plotly.Layout> {
  const base = createInitialLayout(nextFigure);
  if (hasCompatibleTraces(prevFigure, nextFigure)) {
    return {
      ...base,
      ...Objects.pick(prevLayout, PERSISTED_LAYOUT_KEYS),
    };
  }
  // Incompatible traces — only preserve dragmode, not axis settings
  return {
    ...base,
    ...("dragmode" in prevLayout ? { dragmode: prevLayout.dragmode } : {}),
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

  // Track the previous figure to detect trace type changes
  const prevFigureRef = useRef(figure);

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
    const prevFig = prevFigureRef.current;
    prevFigureRef.current = nextFigure;
    setFigure(nextFigure);
    // Start with the new figure's layout, then only preserve user-interaction
    // values (dragmode, xaxis, yaxis) from the previous layout.
    // We don't want to preserve other properties like `shapes` from the previous
    // layout, as they should be fully controlled by the figure prop.
    // When trace types change, axis settings are reset to avoid distortion (#5898).
    setLayout((prev) => computeLayoutOnFigureChange(nextFigure, prevFig, prev));
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
