/* Copyright 2026 Marimo. All rights reserved. */

import type { CellOutputPosition } from "@/core/config/config-schema";

export const CELL_CHROME_VERTICAL_GAP = "gap-0.5";
export const CELL_CHROME_ICON_CLASS = "size-4 opacity-60 hover:opacity-80";

export interface ChromeRailPlacement {
  className: string;
  tooltipSide: "left" | "right";
}

export type OutputChromeControl = "collapse" | "expand" | "fullscreen";

export type OutputChromePlacements = Record<
  OutputChromeControl,
  ChromeRailPlacement
>;

/**
 * Per-control placement for output chrome.
 *
 * Controls that share the same placement are stacked in one rail automatically.
 */
export function getOutputChromePlacements(
  outputPosition: CellOutputPosition | undefined,
): OutputChromePlacements {
  switch (outputPosition) {
    case "left": {
      const stack = {
        className: "left-[-30px] top-8",
        tooltipSide: "right" as const,
      };
      return {
        collapse: stack,
        expand: stack,
        // Left of the create-cell rail, aligned with create-above.
        fullscreen: { className: "left-[-52px] top-0.5", tooltipSide: "right" },
      };
    }
    case "right": {
      const seam = {
        className: "-right-10 top-5 z-30",
        tooltipSide: "right" as const,
      };
      return {
        collapse: seam,
        expand: seam,
        fullscreen: seam,
      };
    }
    default: {
      const outerRight = {
        className: "-right-9 top-1",
        tooltipSide: "left" as const,
      };
      return {
        collapse: outerRight,
        expand: outerRight,
        fullscreen: outerRight,
      };
    }
  }
}

/** Stable identity for a placement, used to group controls into one rail. */
export function chromePlacementKey(placement: ChromeRailPlacement): string {
  return `${placement.className}:${placement.tooltipSide}`;
}

export const cellLeftRailPlacement: ChromeRailPlacement = {
  className: "left-[-26px] justify-between h-full py-1",
  tooltipSide: "right",
};
