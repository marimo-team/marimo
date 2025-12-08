/* Copyright 2024 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";

/**
 * Canvas layout position and size for a cell.
 */
export interface CanvasLayoutCellPosition {
  /**
   * X position (in pixels or canvas units)
   */
  x: number;

  /**
   * Y position (in pixels or canvas units)
   */
  y: number;

  /**
   * Width (in pixels or canvas units)
   */
  w: number;

  /**
   * Height (in pixels or canvas units)
   */
  h: number;

  /**
   * Additional metadata for the cell
   */
  meta?: Record<string, unknown>;
}

/**
 * Serialized canvas layout cell (at rest, without cell IDs).
 */
export interface SerializedCanvasLayoutCell {
  /**
   * The cell position and size.
   * If null, the cell is not in the canvas.
   */
  position: CanvasLayoutCellPosition | null;
}

/**
 * Serialized canvas layout (stored in .canvas.json files).
 */
export interface SerializedCanvasLayout {
  /**
   * The canvas width (in pixels).
   * @default 1200
   */
  width: number;

  /**
   * The canvas height (in pixels).
   * @default 800
   */
  height: number;

  /**
   * The cells in the canvas layout.
   * Cells don't have IDs at rest but are indexed based.
   */
  cells: SerializedCanvasLayoutCell[];

  /**
   * Whether to show grid lines on the canvas
   * @default false
   */
  showGrid?: boolean;

  /**
   * Grid snap size (in pixels)
   * @default 10
   */
  gridSize?: number;
}

/**
 * Canvas layout cell with runtime ID (used during rendering).
 */
export interface CanvasLayoutCell extends CanvasLayoutCellPosition {
  /**
   * The cell ID
   */
  i: CellId;
}

/**
 * Canvas layout (runtime version with cell IDs).
 */
export interface CanvasLayout extends Omit<SerializedCanvasLayout, "cells"> {
  /**
   * The cells in the canvas, mapped to their IDs.
   */
  cells: CanvasLayoutCell[];
}
