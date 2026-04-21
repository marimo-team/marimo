/* Copyright 2026 Marimo. All rights reserved. */

import { z } from "zod";
import type { ICellRendererPlugin } from "../types";
import { SlidesLayoutRenderer } from "./slides-layout";
import type {
  SerializedSlidesLayout,
  SlideConfig,
  SlidesLayout,
} from "./types";
import { Logger } from "@/utils/Logger";
import type { CellId } from "@/core/cells/ids";

/**
 * Plugin definition for the slides layout.
 */
export const SlidesLayoutPlugin: ICellRendererPlugin<
  SerializedSlidesLayout,
  SlidesLayout
> = {
  type: "slides",
  name: "Slides",

  validator: z.object({
    cells: z
      .array(
        z.object({
          type: z.enum(["slide", "sub-slide", "fragment", "skip"]).optional(),
          codeSnippet: z.string().optional(),
        }),
      )
      .optional(),
  }),

  deserializeLayout: (serialized, cells): SlidesLayout => {
    if (serialized.cells?.length === 0) {
      return {
        cells: new Map(),
      };
    }

    if (serialized.cells?.length !== cells.length) {
      Logger.warn(
        "Number of cells in layout does not match number of cells in notebook",
      );
    }

    const slideCells = new Map<CellId, SlideConfig>();
    for (const [idx, cell] of cells.entries()) {
      const slideConfig = serialized.cells?.at(idx);
      if (slideConfig) {
        slideCells.set(cell.id, slideConfig);
      }
    }

    return {
      cells: slideCells,
    };
  },

  serializeLayout: (layout, cells): SerializedSlidesLayout => {
    const serializedCells: SlideConfig[] = cells.map((cell) => {
      const slideConfig = layout.cells.get(cell.id);
      if (!slideConfig) {
        return {};
      }

      const serialized: SlideConfig = {
        // A code snippet is added to help the user / AI understand the cell.
        codeSnippet: `${cell.code.slice(0, 100)}...`,
      };
      // We don't want to save undefined
      if (slideConfig.type) {
        serialized.type = slideConfig.type;
      }
      return serialized;
    });

    return {
      cells: serializedCells,
    };
  },

  Component: SlidesLayoutRenderer,

  getInitialLayout: () => ({
    cells: new Map(),
  }),
};
