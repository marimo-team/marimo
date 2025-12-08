/* Copyright 2024 Marimo. All rights reserved. */

import type { Node } from "@xyflow/react";
import type { CellId } from "@/core/cells/ids";
import type { CellData } from "@/core/cells/types";
import { type CanvasNode, NODE_DEFAULTS } from "./models";
import type {
  CanvasLayout,
  CanvasLayoutCell,
  SerializedCanvasLayout,
  SerializedCanvasLayoutCell,
} from "./types";

/**
 * Get node dimensions, ensuring they are always numbers
 */
export function getNodeDimensions(node: Node): {
  width: number;
  height: number;
} {
  const extractNumber = (value: unknown): number | undefined => {
    if (typeof value === "number") {
      return value;
    }
    if (typeof value === "string") {
      const parsed = Number.parseFloat(value);
      return Number.isNaN(parsed) ? undefined : parsed;
    }
    return undefined;
  };

  return {
    width:
      extractNumber(node.width) ??
      extractNumber(node.style?.width) ??
      NODE_DEFAULTS.width,
    height:
      extractNumber(node.height) ??
      extractNumber(node.style?.height) ??
      NODE_DEFAULTS.height,
  };
}

/**
 * Convert a CanvasLayoutCell to a CanvasNode (react-flow node)
 */
export function layoutCellToNode(cell: CanvasLayoutCell): CanvasNode {
  return {
    id: cell.i,
    type: "cell",
    position: {
      x: cell.x,
      y: cell.y,
    },
    data: {
      cellId: cell.i,
      meta: cell.meta,
    },
    // Store width and height in the node style or data
    style: {
      width: cell.w,
      height: cell.h,
    },
  };
}

/**
 * Convert a CanvasNode to a CanvasLayoutCell
 */
export function nodeToLayoutCell(node: CanvasNode): CanvasLayoutCell {
  const { width, height } = getNodeDimensions(node);

  return {
    i: node.id as CellId,
    x: node.position.x,
    y: node.position.y,
    w: width,
    h: height,
    meta: node.data.meta,
  };
}

/**
 * Convert CanvasLayout to react-flow nodes
 */
export function layoutToNodes(layout: CanvasLayout): Node[] {
  return layout.cells.map(layoutCellToNode);
}

/**
 * Convert react-flow nodes to CanvasLayout
 */
export function nodesToLayout(
  nodes: Node[],
  settings: {
    width: number;
    height: number;
    showGrid?: boolean;
    gridSize?: number;
  },
): CanvasLayout {
  return {
    width: settings.width,
    height: settings.height,
    showGrid: settings.showGrid,
    gridSize: settings.gridSize,
    cells: nodes.map((node) => nodeToLayoutCell(node as CanvasNode)),
  };
}

/**
 * Create initial nodes from cells
 */
export function createInitialNodes(cells: CellData[]): CanvasNode[] {
  const cellWidth = NODE_DEFAULTS.width;
  const cellHeight = NODE_DEFAULTS.height;
  const padding = 40;
  const cellsPerRow = 3;

  return cells.map((cell, index) => {
    const row = Math.floor(index / cellsPerRow);
    const col = index % cellsPerRow;

    return {
      id: cell.id,
      type: "cell" as const,
      position: {
        x: col * (cellWidth + padding) + padding,
        y: row * (cellHeight + padding) + padding,
      },
      data: {
        cellId: cell.id,
        meta: {},
      },
      style: {
        width: cellWidth,
        height: cellHeight,
      },
    };
  });
}

/**
 * Deserialize layout to runtime format with react-flow nodes
 */
export function deserializeCanvasLayout(
  serialized: SerializedCanvasLayout,
  cells: CellData[],
): CanvasLayout {
  const canvasCells: CanvasLayoutCell[] = [];

  for (let i = 0; i < cells.length; i++) {
    const cell = cells[i];
    const serializedCell = serialized.cells[i];

    if (serializedCell?.position) {
      canvasCells.push({
        i: cell.id,
        x: serializedCell.position.x,
        y: serializedCell.position.y,
        w: serializedCell.position.w,
        h: serializedCell.position.h,
        meta: serializedCell.position.meta,
      });
    }
  }

  return {
    width: serialized.width,
    height: serialized.height,
    showGrid: serialized.showGrid ?? true,
    gridSize: serialized.gridSize ?? 20,
    cells: canvasCells,
  };
}

/**
 * Serialize layout to storage format
 */
export function serializeCanvasLayout(
  layout: CanvasLayout,
  cells: CellData[],
): SerializedCanvasLayout {
  const cellPositionMap = new Map(
    layout.cells.map((cell) => [
      cell.i,
      {
        x: cell.x,
        y: cell.y,
        w: cell.w,
        h: cell.h,
        meta: cell.meta,
      },
    ]),
  );

  const serializedCells: SerializedCanvasLayoutCell[] = cells.map((cell) => {
    const position = cellPositionMap.get(cell.id);
    return {
      position: position || null,
    };
  });

  return {
    width: layout.width,
    height: layout.height,
    showGrid: layout.showGrid,
    gridSize: layout.gridSize,
    cells: serializedCells,
  };
}
