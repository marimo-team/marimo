/* Copyright 2024 Marimo. All rights reserved. */
import { ICellRendererPlugin } from "../types";
import {
  GridLayout,
  GridLayoutCellSide,
  SerializedGridLayout,
  SerializedGridLayoutCell,
} from "./types";
import { Logger } from "@/utils/Logger";
import { z } from "zod";
import { Maps } from "@/utils/maps";
import { GridLayoutRenderer } from "./grid-layout";
import { CellId } from "@/core/cells/ids";

/**
 * Plugin definition for the grid layout.
 */

export const GridLayoutPlugin: ICellRendererPlugin<
  SerializedGridLayout,
  GridLayout
> = {
  type: "grid",
  name: "Grid",

  validator: z.object({
    columns: z.number().min(1),
    rowHeight: z.number().min(1),
    maxWidth: z.number().optional(),
    bordered: z.boolean().optional(),
    cells: z.array(
      z.object({
        position: z
          .tuple([z.number(), z.number(), z.number(), z.number()])
          .nullable(),
        scrollable: z.boolean().optional(),
        alignment: z.enum(["top", "bottom", "left", "right"]).optional(),
      }),
    ),
  }),

  deserializeLayout: (serialized, cells): GridLayout => {
    if (serialized.cells.length === 0) {
      return {
        columns: serialized.columns,
        rowHeight: serialized.rowHeight,
        scrollableCells: new Set(),
        cellSide: new Map(),
        cells: [],
      };
    }

    if (serialized.cells.length !== cells.length) {
      Logger.warn(
        "Number of cells in layout does not match number of cells in notebook",
      );
    }

    const scrollableCells = new Set<CellId>();
    const cellSide = new Map<CellId, GridLayoutCellSide>();

    const cellLayouts = serialized.cells.flatMap((cellLayout, idx) => {
      const position = cellLayout.position;
      if (!position) {
        return [];
      }
      const cell = cells[idx];
      if (!cell) {
        return [];
      }
      if (cellLayout.scrollable) {
        scrollableCells.add(cell.id);
      }
      if (cellLayout.side) {
        cellSide.set(cell.id, cellLayout.side);
      }

      return {
        i: cell.id,
        x: position[0],
        y: position[1],
        w: position[2],
        h: position[3],
      };
    });

    return {
      // Grid config
      columns: serialized.columns,
      rowHeight: serialized.rowHeight,
      maxWidth: serialized.maxWidth,
      bordered: serialized.bordered,
      // Cell config
      cells: cellLayouts,
      cellSide: cellSide,
      scrollableCells: scrollableCells,
    };
  },

  serializeLayout: (layout, cells): SerializedGridLayout => {
    const layoutsByKey = Maps.keyBy(layout.cells, (cell) => cell.i);
    const serializedCells: SerializedGridLayoutCell[] = cells.map((cell) => {
      const cellLayout = layoutsByKey.get(cell.id);
      if (!cellLayout) {
        return {
          position: null,
        };
      }
      const out: SerializedGridLayoutCell = {
        position: [cellLayout.x, cellLayout.y, cellLayout.w, cellLayout.h],
      };
      if (layout.scrollableCells.has(cell.id)) {
        out.scrollable = true;
      }
      if (layout.cellSide.has(cell.id)) {
        out.side = layout.cellSide.get(cell.id);
      }
      return out;
    });

    return {
      // Grid config
      columns: layout.columns,
      rowHeight: layout.rowHeight,
      maxWidth: layout.maxWidth,
      bordered: layout.bordered,
      // Cell config
      cells: serializedCells,
    };
  },

  Component: GridLayoutRenderer,

  getInitialLayout: () => ({
    // Grid config
    columns: 24,
    rowHeight: 20,
    maxWidth: 1400,
    bordered: true,
    // Cell config
    scrollableCells: new Set(),
    cellSide: new Map(),
    cells: [],
  }),
};
