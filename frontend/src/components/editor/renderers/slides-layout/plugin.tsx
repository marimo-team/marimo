/* Copyright 2026 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";
import { Logger } from "@/utils/Logger";
import type { ICellRendererPlugin } from "../types";
import { SlidesLayoutRenderer } from "./slides-layout";
import {
  type SerializedSlidesLayout,
  type SlideConfig,
  type SlidesLayout,
  SlidesLayoutSchema,
} from "./types";

/**
 * Plugin definition for the slides layout.
 */
export const SlidesLayoutPlugin: ICellRendererPlugin<
  SerializedSlidesLayout,
  SlidesLayout
> = {
  type: "slides",
  name: "Slides",
  validator: SlidesLayoutSchema,

  deserializeLayout: (serialized, cells): SlidesLayout => {
    const serializedCells = serialized.cells ?? [];
    const deck = serialized.deck ?? {};

    if (serializedCells.length > 0 && serializedCells.length !== cells.length) {
      Logger.warn(
        "Number of cells in layout does not match number of cells in notebook",
      );
    }

    const slideCells = new Map<CellId, SlideConfig>();
    for (const [idx, cell] of cells.entries()) {
      const slideConfig = serializedCells.at(idx);
      if (slideConfig) {
        slideCells.set(cell.id, slideConfig);
      }
    }

    return { cells: slideCells, deck };
  },

  serializeLayout: (layout, cells): SerializedSlidesLayout => ({
    cells: cells.map((cell) => ({
      ...layout.cells.get(cell.id),
    })),
    deck: layout.deck,
  }),

  Component: SlidesLayoutRenderer,

  getInitialLayout: () => ({
    cells: new Map(),
    deck: {},
  }),
};
