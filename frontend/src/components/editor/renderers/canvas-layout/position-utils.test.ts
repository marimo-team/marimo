/* Copyright 2024 Marimo. All rights reserved. */

import type { Node } from "@xyflow/react";
import { describe, expect, it } from "vitest";
import { NODE_DEFAULTS } from "./models";
import { findOpenSpace } from "./position-utils";

describe("findOpenSpace", () => {
  it("should return the starting position when no nodes exist", () => {
    const result = findOpenSpace(100, 100, []);
    expect(result).toEqual({ x: 100, y: 100 });
  });

  it("should return the starting position when it is free", () => {
    const nodes: Node[] = [
      {
        id: "1",
        type: "cell",
        position: { x: 1000, y: 1000 },
        data: {},
        width: NODE_DEFAULTS.width,
        height: NODE_DEFAULTS.height,
      },
    ];

    const result = findOpenSpace(100, 100, nodes);
    expect(result).toEqual({ x: 100, y: 100 });
  });

  it("should find open space to the right when starting position is occupied", () => {
    const nodes: Node[] = [
      {
        id: "1",
        type: "cell",
        position: { x: 100, y: 100 },
        data: {},
        width: NODE_DEFAULTS.width,
        height: NODE_DEFAULTS.height,
      },
    ];

    // Try to place at the same position - should find space to the right or elsewhere
    const result = findOpenSpace(100, 100, nodes);

    // Should not be at the exact starting position (allowing for some search)
    const isAtStartingPosition = result.x === 100 && result.y === 100;
    expect(isAtStartingPosition).toBe(false);
  });

  it("should find open space when multiple cells are present", () => {
    const nodes: Node[] = [
      {
        id: "1",
        type: "cell",
        position: { x: 100, y: 100 },
        data: {},
        width: NODE_DEFAULTS.width,
        height: NODE_DEFAULTS.height,
      },
      {
        id: "2",
        type: "cell",
        position: { x: 540, y: 100 }, // NODE_DEFAULTS.width (400) + margin (40) + some spacing
        data: {},
        width: NODE_DEFAULTS.width,
        height: NODE_DEFAULTS.height,
      },
    ];

    // Try to place between the two cells
    const result = findOpenSpace(300, 100, nodes);

    // Should find a position that doesn't overlap with either cell (with margin)
    const margin = 40;
    const overlapsWithCell1 =
      result.x < 100 + NODE_DEFAULTS.width + margin &&
      result.x + NODE_DEFAULTS.width + margin > 100 &&
      result.y < 100 + NODE_DEFAULTS.height + margin &&
      result.y + NODE_DEFAULTS.height + margin > 100;

    const overlapsWithCell2 =
      result.x < 540 + NODE_DEFAULTS.width + margin &&
      result.x + NODE_DEFAULTS.width + margin > 540 &&
      result.y < 100 + NODE_DEFAULTS.height + margin &&
      result.y + NODE_DEFAULTS.height + margin > 100;

    expect(overlapsWithCell1).toBe(false);
    expect(overlapsWithCell2).toBe(false);
  });

  it("should respect the margin parameter", () => {
    const nodes: Node[] = [
      {
        id: "1",
        type: "cell",
        position: { x: 100, y: 100 },
        data: {},
        width: NODE_DEFAULTS.width,
        height: NODE_DEFAULTS.height,
      },
    ];

    const margin = 100; // Large margin
    const result = findOpenSpace(100, 100, nodes, margin);

    // Should find a position with enough margin (not at the exact starting position)
    const isAtStartingPosition = result.x === 100 && result.y === 100;
    expect(isAtStartingPosition).toBe(false);
  });

  it("should search in a spiral pattern and find open space", () => {
    // Create a few cells to force searching through multiple positions
    const nodes: Node[] = [
      {
        id: "1",
        type: "cell",
        position: { x: 100, y: 100 },
        data: {},
        width: NODE_DEFAULTS.width,
        height: NODE_DEFAULTS.height,
      },
      {
        id: "2",
        type: "cell",
        position: { x: 540, y: 100 }, // To the right
        data: {},
        width: NODE_DEFAULTS.width,
        height: NODE_DEFAULTS.height,
      },
    ];

    // Try to place at a position occupied by the first cell
    const result = findOpenSpace(100, 100, nodes);

    // Should find a position that doesn't overlap with any cell
    const margin = 40;
    const overlapsWithAny = nodes.some((node) => {
      const xOverlap =
        result.x < node.position.x + NODE_DEFAULTS.width + margin &&
        result.x + NODE_DEFAULTS.width + margin > node.position.x;
      const yOverlap =
        result.y < node.position.y + NODE_DEFAULTS.height + margin &&
        result.y + NODE_DEFAULTS.height + margin > node.position.y;
      return xOverlap && yOverlap;
    });

    expect(overlapsWithAny).toBe(false);
  });

  it("should keep positions positive", () => {
    const nodes: Node[] = [
      {
        id: "1",
        type: "cell",
        position: { x: 40, y: 40 },
        data: {},
        width: NODE_DEFAULTS.width,
        height: NODE_DEFAULTS.height,
      },
    ];

    // Try to place very close to origin
    const result = findOpenSpace(50, 50, nodes);

    // Result should have positive coordinates
    expect(result.x).toBeGreaterThanOrEqual(0);
    expect(result.y).toBeGreaterThanOrEqual(0);
  });

  it("should find space efficiently with many nodes", () => {
    // Create 20 nodes in a horizontal line
    const nodes: Node[] = [];
    for (let i = 0; i < 20; i++) {
      nodes.push({
        id: `${i}`,
        type: "cell",
        position: {
          x: i * (NODE_DEFAULTS.width + 40),
          y: 100,
        },
        data: {},
        width: NODE_DEFAULTS.width,
        height: NODE_DEFAULTS.height,
      });
    }

    // Try to place at the start - should find space below or above
    const result = findOpenSpace(100, 100, nodes);

    // Should not overlap with any existing node
    const margin = 40;
    const overlaps = nodes.some((node) => {
      const xOverlap =
        result.x < node.position.x + NODE_DEFAULTS.width + margin &&
        result.x + NODE_DEFAULTS.width + margin > node.position.x;
      const yOverlap =
        result.y < node.position.y + NODE_DEFAULTS.height + margin &&
        result.y + NODE_DEFAULTS.height + margin > node.position.y;
      return xOverlap && yOverlap;
    });

    expect(overlaps).toBe(false);
  });

  it("should provide a fallback position when all nearby spaces are occupied", () => {
    // Create a very dense grid of cells
    const nodes: Node[] = [];
    for (let i = 0; i < 10; i++) {
      for (let j = 0; j < 10; j++) {
        nodes.push({
          id: `${i}-${j}`,
          type: "cell",
          position: {
            x: i * (NODE_DEFAULTS.width + 40),
            y: j * (NODE_DEFAULTS.height + 40),
          },
          data: {},
          width: NODE_DEFAULTS.width,
          height: NODE_DEFAULTS.height,
        });
      }
    }

    // Try to place in the middle - should still return a position
    const result = findOpenSpace(500, 500, nodes);

    // Should return some position (fallback if needed)
    expect(result).toBeDefined();
    expect(typeof result.x).toBe("number");
    expect(typeof result.y).toBe("number");
  });
});
