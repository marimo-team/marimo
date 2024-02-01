/* Copyright 2024 Marimo. All rights reserved. */

import { CellId } from "@/core/cells/ids";

/**
 * The serialized form of a grid layout.
 * This must be backwards-compatible as it is stored on the user's disk.
 */
export interface SerializedGridLayout {
  /**
   * The number of columns.
   * @default 12
   *
   * This is currently hardcoded and not settable by the user.
   * In future, we may want to allow the user to set this.
   */
  columns: number;

  /**
   * The height of a row, in pixels.
   *
   * This is currently hardcoded and not settable by the user.
   * In future, we may want to allow the user to set this.
   */
  rowHeight: number;

  /**
   * The max-width of the grid layout.
   */
  maxWidth?: number;

  /**
   * The cells in the layout.
   * Cells don't have IDs at rest but are indexed based.
   *
   * Once we load the layout, we assign IDs to the cells so that we can
   * track as they move around.
   */
  cells: SerializedGridLayoutCell[];

  /**
   * Bordered grid
   */
  bordered?: boolean;
}

export interface SerializedGridLayoutCell {
  /**
   * The cell position, as [x, y, w, h].
   * If null, the cell is not in the layout.
   */
  position: SerializedGridLayoutCellPosition | null;

  /**
   * True if the cell is scrollable.
   */
  scrollable?: boolean;

  /**
   * The cell's alignment.
   */
  side?: GridLayoutCellSide;
}

export type GridLayoutCellSide = "top" | "left" | "right" | "bottom";

export interface GridLayout extends Omit<SerializedGridLayout, "cells"> {
  /**
   * The cells in the layout.
   */
  cells: Array<{
    i: string;
    x: number;
    y: number;
    w: number;
    h: number;
  }>;

  scrollableCells: Set<CellId>;

  cellSide: Map<CellId, GridLayoutCellSide>;
}

export type SerializedGridLayoutCellPosition = [
  x: number,
  y: number,
  w: number,
  h: number,
];
