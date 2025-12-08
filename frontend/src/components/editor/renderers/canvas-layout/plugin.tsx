/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";
import type { CellData } from "@/core/cells/types";
import type { ICellRendererPlugin } from "../types";
import { CanvasLayoutRenderer } from "./canvas-layout";
import type { CanvasLayout, SerializedCanvasLayout } from "./types";
import {
  createInitialNodes,
  deserializeCanvasLayout,
  nodeToLayoutCell,
  serializeCanvasLayout,
} from "./utils";

const DEFAULT_WIDTH = 1600;
const DEFAULT_HEIGHT = 1200;
const DEFAULT_GRID_SIZE = 20;

/**
 * Canvas layout plugin.
 * Provides a free-form canvas where cells can be positioned anywhere using react-flow.
 */
export const CanvasLayoutPlugin: ICellRendererPlugin<
  SerializedCanvasLayout,
  CanvasLayout
> = {
  type: "canvas",
  name: "Canvas",

  validator: z.object({
    width: z.number().min(1),
    height: z.number().min(1),
    showGrid: z.boolean().optional(),
    gridSize: z.number().min(1).optional(),
    cells: z.array(
      z.object({
        position: z
          .object({
            x: z.number(),
            y: z.number(),
            w: z.number().min(1),
            h: z.number().min(1),
            meta: z.record(z.string(), z.unknown()).optional(),
          })
          .nullable(),
      }),
    ),
  }),

  deserializeLayout: (
    serialized: SerializedCanvasLayout,
    cells: CellData[],
  ): CanvasLayout => {
    return deserializeCanvasLayout(serialized, cells);
  },

  serializeLayout: (
    layout: CanvasLayout,
    cells: CellData[],
  ): SerializedCanvasLayout => {
    return serializeCanvasLayout(layout, cells);
  },

  Component: CanvasLayoutRenderer,

  getInitialLayout: (cells: CellData[]): CanvasLayout => {
    const nodes = createInitialNodes(cells);
    const canvasCells = nodes.map((node) => nodeToLayoutCell(node));

    // Calculate canvas dimensions based on cells
    const maxX = Math.max(
      ...canvasCells.map((cell) => cell.x + cell.w),
      DEFAULT_WIDTH,
    );
    const maxY = Math.max(
      ...canvasCells.map((cell) => cell.y + cell.h),
      DEFAULT_HEIGHT,
    );

    const padding = 40;

    return {
      width: maxX + padding,
      height: maxY + padding,
      showGrid: true,
      gridSize: DEFAULT_GRID_SIZE,
      cells: canvasCells,
    };
  },
};
