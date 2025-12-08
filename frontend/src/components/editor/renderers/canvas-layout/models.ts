/* Copyright 2024 Marimo. All rights reserved. */

import type { Edge, Node } from "@xyflow/react";
import type { CellId } from "@/core/cells/ids";

/**
 * Canvas node position and metadata
 */
export interface CanvasNodeData extends Record<string, unknown> {
  /**
   * The cell ID
   */
  cellId: CellId;

  /**
   * Additional metadata for the node
   */
  meta?: Record<string, unknown>;
}

/**
 * Canvas node (extends react-flow Node)
 */
export interface CanvasNode extends Node<CanvasNodeData, "cell"> {
  type: "cell";
}

/**
 * Canvas edge (extends react-flow Edge)
 */
export interface CanvasEdge extends Edge {
  // Can be extended with custom edge properties later
}

/**
 * Canvas viewport state
 */
export interface CanvasViewport {
  x: number;
  y: number;
  zoom: number;
}

/**
 * Data flow direction for edges
 */
export type DataFlowDirection = "left-right" | "top-down";

/**
 * Interaction mode for the canvas
 */
export type InteractionMode = "pointer" | "hand";

/**
 * Canvas settings
 */
export interface CanvasSettings {
  /**
   * Grid size in pixels
   */
  gridSize: number;

  /**
   * Whether to snap to grid
   */
  snapToGrid: boolean;

  /**
   * Whether to show minimap
   */
  showMinimap: boolean;

  /**
   * Data flow direction for edges
   * @default "left-right"
   */
  dataFlow: DataFlowDirection;

  /**
   * Interaction mode for the canvas
   * @default "pointer"
   */
  interactionMode: InteractionMode;

  /**
   * Whether to show debug info (node dimensions)
   * @default false
   */
  debug: boolean;
}

/**
 * Default node dimensions - single source of truth
 */
export const NODE_DEFAULTS = {
  width: 600,
  height: 60,
  minWidth: 200,
  minHeight: 60,
} as const;
