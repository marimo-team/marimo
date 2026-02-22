/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import type { Data } from "../matplotlib-renderer";
import { visibleForTesting } from "../matplotlib-renderer";

const {
  pixelToData,
  dataToPixel,
  pointInPolygon,
  clampToAxes,
  isPointInBox,
  isInAxes,
} = visibleForTesting;

// A simple axes geometry for testing:
// axes occupy pixels [100, 50] to [500, 350] (400px wide, 300px tall)
// data range x: [0, 10], y: [0, 100]
const LINEAR_AXES: Pick<
  Data,
  "axesPixelBounds" | "xBounds" | "xScale" | "yBounds" | "yScale"
> = {
  axesPixelBounds: [100, 50, 500, 350],
  xBounds: [0, 10],
  yBounds: [0, 100],
  xScale: "linear",
  yScale: "linear",
};

const LOG_AXES: Pick<
  Data,
  "axesPixelBounds" | "xBounds" | "xScale" | "yBounds" | "yScale"
> = {
  axesPixelBounds: [100, 50, 500, 350],
  xBounds: [1, 1000],
  yBounds: [1, 1000],
  xScale: "log",
  yScale: "log",
};

describe("pixelToData", () => {
  it("maps top-left of axes to (xMin, yMax)", () => {
    const result = pixelToData({ x: 100, y: 50 }, LINEAR_AXES);
    expect(result.x).toBeCloseTo(0);
    expect(result.y).toBeCloseTo(100);
  });

  it("maps bottom-right of axes to (xMax, yMin)", () => {
    const result = pixelToData({ x: 500, y: 350 }, LINEAR_AXES);
    expect(result.x).toBeCloseTo(10);
    expect(result.y).toBeCloseTo(0);
  });

  it("maps center of axes to midpoint of data range", () => {
    const result = pixelToData({ x: 300, y: 200 }, LINEAR_AXES);
    expect(result.x).toBeCloseTo(5);
    expect(result.y).toBeCloseTo(50);
  });
});

describe("dataToPixel", () => {
  it("maps (xMin, yMax) to top-left of axes", () => {
    const result = dataToPixel({ x: 0, y: 100 }, LINEAR_AXES);
    expect(result.x).toBeCloseTo(100);
    expect(result.y).toBeCloseTo(50);
  });

  it("maps (xMax, yMin) to bottom-right of axes", () => {
    const result = dataToPixel({ x: 10, y: 0 }, LINEAR_AXES);
    expect(result.x).toBeCloseTo(500);
    expect(result.y).toBeCloseTo(350);
  });
});

describe("pixelToData / dataToPixel roundtrip", () => {
  it("roundtrips linear coordinates", () => {
    const pixel = { x: 250, y: 175 };
    const data = pixelToData(pixel, LINEAR_AXES);
    const back = dataToPixel(data, LINEAR_AXES);
    expect(back.x).toBeCloseTo(pixel.x);
    expect(back.y).toBeCloseTo(pixel.y);
  });

  it("roundtrips log coordinates", () => {
    const pixel = { x: 300, y: 200 };
    const data = pixelToData(pixel, LOG_AXES);
    const back = dataToPixel(data, LOG_AXES);
    expect(back.x).toBeCloseTo(pixel.x);
    expect(back.y).toBeCloseTo(pixel.y);
  });
});

describe("pointInPolygon", () => {
  // Triangle with vertices at (0,0), (10,0), (5,10)
  const triangle = [
    { x: 0, y: 0 },
    { x: 10, y: 0 },
    { x: 5, y: 10 },
  ];

  it("returns true for a point inside", () => {
    expect(pointInPolygon({ x: 5, y: 3 }, triangle)).toBe(true);
  });

  it("returns false for a point outside", () => {
    expect(pointInPolygon({ x: 20, y: 20 }, triangle)).toBe(false);
  });

  it("returns false for a point just outside a side", () => {
    expect(pointInPolygon({ x: 0, y: 5 }, triangle)).toBe(false);
  });
});

describe("clampToAxes", () => {
  it("does not change a point inside the axes", () => {
    const result = clampToAxes({ x: 300, y: 200 }, LINEAR_AXES);
    expect(result).toEqual({ x: 300, y: 200 });
  });

  it("clamps a point left of axes to left edge", () => {
    const result = clampToAxes({ x: 50, y: 200 }, LINEAR_AXES);
    expect(result.x).toBe(100);
    expect(result.y).toBe(200);
  });

  it("clamps a point above axes to top edge", () => {
    const result = clampToAxes({ x: 300, y: 10 }, LINEAR_AXES);
    expect(result.x).toBe(300);
    expect(result.y).toBe(50);
  });

  it("clamps a point beyond bottom-right to corner", () => {
    const result = clampToAxes({ x: 600, y: 400 }, LINEAR_AXES);
    expect(result).toEqual({ x: 500, y: 350 });
  });
});

describe("isPointInBox", () => {
  const boxStart = { x: 10, y: 10 };
  const boxEnd = { x: 50, y: 50 };

  it("returns true for a point inside", () => {
    expect(isPointInBox({ x: 30, y: 30 }, boxStart, boxEnd)).toBe(true);
  });

  it("returns true for a point on the edge", () => {
    expect(isPointInBox({ x: 10, y: 30 }, boxStart, boxEnd)).toBe(true);
  });

  it("returns false for a point outside", () => {
    expect(isPointInBox({ x: 5, y: 30 }, boxStart, boxEnd)).toBe(false);
  });

  it("works regardless of start/end order", () => {
    // Swap start and end (end is top-left, start is bottom-right)
    expect(isPointInBox({ x: 30, y: 30 }, boxEnd, boxStart)).toBe(true);
    expect(isPointInBox({ x: 5, y: 30 }, boxEnd, boxStart)).toBe(false);
  });
});

describe("isInAxes", () => {
  it("returns true for a point inside the axes", () => {
    expect(isInAxes({ x: 300, y: 200 }, LINEAR_AXES)).toBe(true);
  });

  it("returns true for a point on the boundary", () => {
    expect(isInAxes({ x: 100, y: 50 }, LINEAR_AXES)).toBe(true); // top-left
    expect(isInAxes({ x: 500, y: 350 }, LINEAR_AXES)).toBe(true); // bottom-right
    expect(isInAxes({ x: 100, y: 350 }, LINEAR_AXES)).toBe(true); // bottom-left
    expect(isInAxes({ x: 500, y: 50 }, LINEAR_AXES)).toBe(true); // top-right
  });

  it("returns false for a point left of axes", () => {
    expect(isInAxes({ x: 99, y: 200 }, LINEAR_AXES)).toBe(false);
  });

  it("returns false for a point right of axes", () => {
    expect(isInAxes({ x: 501, y: 200 }, LINEAR_AXES)).toBe(false);
  });

  it("returns false for a point above axes", () => {
    expect(isInAxes({ x: 300, y: 49 }, LINEAR_AXES)).toBe(false);
  });

  it("returns false for a point below axes", () => {
    expect(isInAxes({ x: 300, y: 351 }, LINEAR_AXES)).toBe(false);
  });
});
