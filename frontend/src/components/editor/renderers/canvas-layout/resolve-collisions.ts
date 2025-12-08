/* Copyright 2024 Marimo. All rights reserved. */

import type { Edge, Node } from "@xyflow/react";
import { type SpatialBounds, SpatialHash } from "./spatial-hash";
import { getNodeDimensions } from "./utils";

interface CollisionResolutionOptions {
  /**
   * Maximum number of iterations to try resolving collisions
   * @default 10
   */
  maxIterations?: number;
  /**
   * Overlap threshold (0-1). 0 = any overlap, 1 = complete overlap
   * @default 0.5
   */
  overlapThreshold?: number;
  /**
   * Minimum margin between nodes in pixels
   * @default 10
   */
  margin?: number;
  /**
   * Grid size for snapping (if snap-to-grid is enabled)
   * @default undefined (no snapping)
   */
  gridSize?: number;
  /**
   * IDs of selected nodes (treated as rigid body)
   * @default undefined
   */
  selectedNodeIds?: Set<string>;
  /**
   * Edges between nodes (for edge-aware collision)
   * @default undefined
   */
  edges?: Edge[];
}

interface NodeBounds extends SpatialBounds {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Get the bounds of a node including margin
 */
function getNodeBounds(node: Node, margin: number): NodeBounds {
  const { width, height } = getNodeDimensions(node);

  return {
    id: node.id,
    x: node.position.x - margin,
    y: node.position.y - margin,
    width: width + margin * 2,
    height: height + margin * 2,
  };
}

/**
 * Check if two nodes overlap and calculate overlap amount
 */
function getOverlap(
  a: NodeBounds,
  b: NodeBounds,
): { overlaps: boolean; overlapX: number; overlapY: number } {
  const overlapX = Math.max(
    0,
    Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x),
  );
  const overlapY = Math.max(
    0,
    Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y),
  );

  const overlaps = overlapX > 0 && overlapY > 0;

  return { overlaps, overlapX, overlapY };
}

/**
 * Calculate the overlap ratio between two nodes
 */
function getOverlapRatio(a: NodeBounds, b: NodeBounds): number {
  const { overlaps, overlapX, overlapY } = getOverlap(a, b);

  if (!overlaps) {
    return 0;
  }

  const overlapArea = overlapX * overlapY;
  const aArea = a.width * a.height;
  const bArea = b.width * b.height;
  const minArea = Math.min(aArea, bArea);

  return overlapArea / minArea;
}

/**
 * Check if two nodes are connected by an edge
 */
function areConnected(
  nodeA: string,
  nodeB: string,
  edges: Edge[] | undefined,
): boolean {
  if (!edges) {
    return false;
  }

  return edges.some(
    (edge) =>
      (edge.source === nodeA && edge.target === nodeB) ||
      (edge.source === nodeB && edge.target === nodeA),
  );
}

/**
 * Get preferred movement direction based on edge connections
 * If nodes are connected, prefer moving perpendicular to the edge
 */
function getPreferredMoveDirection(
  a: NodeBounds,
  b: NodeBounds,
  overlapX: number,
  overlapY: number,
  edges: Edge[] | undefined,
): "horizontal" | "vertical" {
  const connected = areConnected(a.id, b.id, edges);

  if (connected) {
    // For connected nodes, move perpendicular to the edge direction
    const dx = Math.abs(a.x + a.width / 2 - (b.x + b.width / 2));
    const dy = Math.abs(a.y + a.height / 2 - (b.y + b.height / 2));

    // If edge is more horizontal, move vertically (and vice versa)
    return dx > dy ? "vertical" : "horizontal";
  }

  // Default: move along axis with less overlap
  return overlapX < overlapY ? "horizontal" : "vertical";
}

/**
 * Snap a position to grid
 */
function snapToGrid(position: number, gridSize: number): number {
  return Math.round(position / gridSize) * gridSize;
}

/**
 * Resolve collisions between nodes by moving them apart
 * Advanced features:
 * - Selection-aware: Selected nodes move as rigid body
 * - Grid snap: Respects snap-to-grid settings
 * - Edge-aware: Considers edges when determining move direction
 * - Spatial hashing: O(n) performance with many nodes
 */
export function resolveCollisions(
  nodes: Node[],
  options: CollisionResolutionOptions = {},
): Node[] {
  const {
    maxIterations = 10,
    overlapThreshold = 0.5,
    margin = 10,
    gridSize,
    selectedNodeIds,
    edges,
  } = options;

  let currentNodes = [...nodes];
  let hasCollisions = true;
  let iterations = 0;

  while (hasCollisions && iterations < maxIterations) {
    hasCollisions = false;

    // Use spatial hashing for efficient collision detection
    const spatialHash = new SpatialHash(400); // Cell size = 400px
    const nodeBounds = currentNodes.map((node) => getNodeBounds(node, margin));

    // Create index map for O(1) lookup performance
    const boundsIndexMap = new Map<string, number>();
    for (let i = 0; i < nodeBounds.length; i++) {
      boundsIndexMap.set(nodeBounds[i].id, i);
    }

    // Insert all nodes into spatial hash
    for (const bounds of nodeBounds) {
      spatialHash.insert(bounds);
    }

    // Find all colliding pairs using spatial hash
    const collisions: Array<[number, number]> = [];

    for (let i = 0; i < nodeBounds.length; i++) {
      const boundsA = nodeBounds[i];
      const nearby = spatialHash.getNearby(boundsA);

      for (const boundsB of nearby) {
        const j = boundsIndexMap.get(boundsB.id);

        if (j !== undefined && j > i) {
          // Only check each pair once
          const ratio = getOverlapRatio(boundsA, boundsB);
          if (ratio > overlapThreshold) {
            collisions.push([i, j]);
            hasCollisions = true;
          }
        }
      }
    }

    if (!hasCollisions) {
      break;
    }

    // Resolve collisions by moving nodes apart
    const adjustments = new Map<number, { x: number; y: number }>();

    for (const [i, j] of collisions) {
      const a = nodeBounds[i];
      const b = nodeBounds[j];
      const { overlapX, overlapY } = getOverlap(a, b);

      // Check if nodes are selected
      const aSelected = selectedNodeIds?.has(a.id) ?? false;
      const bSelected = selectedNodeIds?.has(b.id) ?? false;

      // If both nodes are selected, skip collision resolution (maintain rigid body)
      if (aSelected && bSelected) {
        continue;
      }

      // Selection-aware collision:
      // If only one selected, only move the non-selected one
      // If neither selected, move both equally
      let aMoveRatio = 0.5;
      let bMoveRatio = 0.5;

      if (aSelected && !bSelected) {
        // Only move b
        aMoveRatio = 0;
        bMoveRatio = 1;
      } else if (bSelected && !aSelected) {
        // Only move a
        aMoveRatio = 1;
        bMoveRatio = 0;
      }

      // Determine direction to move nodes (edge-aware)
      const moveDirection = getPreferredMoveDirection(
        a,
        b,
        overlapX,
        overlapY,
        edges,
      );

      const adjA = adjustments.get(i) ?? { x: 0, y: 0 };
      const adjB = adjustments.get(j) ?? { x: 0, y: 0 };

      if (moveDirection === "horizontal") {
        // Move horizontally
        const direction = a.x < b.x ? -1 : 1;
        const moveAmount = overlapX;

        adjA.x += moveAmount * direction * aMoveRatio;
        adjB.x -= moveAmount * direction * bMoveRatio;
      } else {
        // Move vertically
        const direction = a.y < b.y ? -1 : 1;
        const moveAmount = overlapY;

        adjA.y += moveAmount * direction * aMoveRatio;
        adjB.y -= moveAmount * direction * bMoveRatio;
      }

      adjustments.set(i, adjA);
      adjustments.set(j, adjB);
    }

    // Apply adjustments
    currentNodes = currentNodes.map((node, index) => {
      const adjustment = adjustments.get(index);
      if (!adjustment) {
        return node;
      }

      let newX = node.position.x + adjustment.x;
      let newY = node.position.y + adjustment.y;

      // Apply grid snapping if enabled
      if (gridSize) {
        newX = snapToGrid(newX, gridSize);
        newY = snapToGrid(newY, gridSize);
      }

      return {
        ...node,
        position: {
          x: newX,
          y: newY,
        },
      };
    });

    iterations++;
  }

  return currentNodes;
}
