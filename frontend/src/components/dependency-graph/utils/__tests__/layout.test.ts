/* Copyright 2026 Marimo. All rights reserved. */

import type { Node } from "reactflow";
import { describe, expect, it } from "vitest";
import type { NodeData } from "../../elements";
import { boundingBox, placeIslands } from "../layout";

function node(
  id: string,
  x: number,
  y: number,
  width: number,
  height: number,
): Node<NodeData> {
  return {
    id,
    position: { x, y },
    width,
    height,
    data: { atom: {} as NodeData["atom"], defs: [] },
  };
}

describe("boundingBox", () => {
  it("is all-zero for an empty set", () => {
    expect(boundingBox([])).toEqual({ minX: 0, minY: 0, maxX: 0, maxY: 0 });
  });

  it("spans position + size across nodes", () => {
    const box = boundingBox([
      node("a", 0, 0, 50, 50),
      node("b", 10, 20, 100, 40),
    ]);
    expect(box).toEqual({ minX: 0, minY: 0, maxX: 110, maxY: 60 });
  });

  it("reads size from style.width/height when width/height are absent", () => {
    const groupNode: Node = {
      id: "g",
      position: { x: 5, y: 5 },
      data: {},
      style: { width: 200, height: 100 },
    };
    expect(boundingBox([groupNode])).toEqual({
      minX: 5,
      minY: 5,
      maxX: 205,
      maxY: 105,
    });
  });
});

describe("placeIslands", () => {
  it("returns nothing when there are no islands", () => {
    expect(placeIslands([], [node("a", 0, 0, 100, 100)])).toEqual([]);
  });

  it("stacks islands in a column to the right of the placed graph", () => {
    const placed = [node("main", 0, 0, 200, 300)];
    const islands = [node("i0", 0, 0, 90, 40), node("i1", 0, 0, 90, 40)];
    const result = placeIslands(islands, placed);
    // startX = maxX(200) + margin(40) = 240; startY = minY(0).
    expect(result[0].position).toEqual({ x: 240, y: 0 });
    // Second island stacked below the first (height 40 + gap 20).
    expect(result[1].position).toEqual({ x: 240, y: 60 });
  });

  it("wraps into a new column when the column gets too tall", () => {
    const placed = [node("main", 0, 0, 200, 300)];
    const islands = Array.from({ length: 10 }, (_, i) =>
      node(`i${i}`, 0, 0, 90, 40),
    );
    const result = placeIslands(islands, placed);
    const firstColumnX = result[0].position.x;
    const wrapped = result.find((n) => n.position.x > firstColumnX);
    expect(wrapped).toBeDefined();
  });
});
