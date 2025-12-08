/* Copyright 2024 Marimo. All rights reserved. */

import type { Node } from "@xyflow/react";
import { NODE_DEFAULTS } from "./models";
import { SpatialHash } from "./spatial-hash";
import { getNodeDimensions } from "./utils";

/**
 * Find open space near a starting position, avoiding collisions with existing nodes.
 * Uses spatial hashing for efficient collision detection.
 *
 * @param startX - Starting X position
 * @param startY - Starting Y position
 * @param nodes - Existing nodes to avoid
 * @param margin - Minimum margin between nodes (default: 40)
 * @returns Position with open space
 */
export function findOpenSpace(
  startX: number,
  startY: number,
  nodes: Node[],
  margin: number = 40,
): { x: number; y: number } {
  const cellWidth = NODE_DEFAULTS.width;
  const cellHeight = NODE_DEFAULTS.height;

  // Build spatial hash for efficient collision detection
  const spatialHash = new SpatialHash(400);
  for (const node of nodes) {
    const { width, height } = getNodeDimensions(node);
    spatialHash.insert({
      id: node.id,
      x: node.position.x - margin,
      y: node.position.y - margin,
      width: width + margin * 2,
      height: height + margin * 2,
    });
  }

  // Helper to check if a position is free
  const isPositionFree = (x: number, y: number): boolean => {
    const testBounds = {
      id: "test",
      x: x - margin,
      y: y - margin,
      width: cellWidth + margin * 2,
      height: cellHeight + margin * 2,
    };

    const nearby = spatialHash.getNearby(testBounds);
    for (const bounds of nearby) {
      // Check for overlap
      const overlapX =
        Math.min(testBounds.x + testBounds.width, bounds.x + bounds.width) -
        Math.max(testBounds.x, bounds.x);
      const overlapY =
        Math.min(testBounds.y + testBounds.height, bounds.y + bounds.height) -
        Math.max(testBounds.y, bounds.y);

      if (overlapX > 0 && overlapY > 0) {
        return false;
      }
    }

    return true;
  };

  // Try the starting position first
  if (isPositionFree(startX, startY)) {
    return { x: startX, y: startY };
  }

  // Search in a spiral pattern for open space
  const searchDistance = cellWidth + margin;
  const maxSearchRadius = 5; // Search up to 5 positions in each direction

  for (let radius = 1; radius <= maxSearchRadius; radius++) {
    // Try positions in a spiral: right, down, left, up
    const positions = [
      // Right
      { x: startX + radius * searchDistance, y: startY },
      // Down
      { x: startX, y: startY + radius * searchDistance },
      // Left (but keep x positive)
      { x: Math.max(margin, startX - radius * searchDistance), y: startY },
      // Up (but keep y positive)
      { x: startX, y: Math.max(margin, startY - radius * searchDistance) },
      // Diagonal positions
      {
        x: startX + radius * searchDistance,
        y: startY + radius * searchDistance,
      },
      {
        x: Math.max(margin, startX - radius * searchDistance),
        y: startY + radius * searchDistance,
      },
      {
        x: startX + radius * searchDistance,
        y: Math.max(margin, startY - radius * searchDistance),
      },
      {
        x: Math.max(margin, startX - radius * searchDistance),
        y: Math.max(margin, startY - radius * searchDistance),
      },
    ];

    for (const pos of positions) {
      if (isPositionFree(pos.x, pos.y)) {
        return pos;
      }
    }
  }

  // Fallback: just offset from the start position
  return { x: startX + searchDistance, y: startY + searchDistance };
}
