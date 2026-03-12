/* Copyright 2026 Marimo. All rights reserved. */

import type * as Plotly from "plotly.js";
import { describe, expect, it } from "vitest";
import type { Figure } from "../Plot";
import {
  computeLayoutOnFigureChange,
  computeLayoutUpdate,
  computeOmitKeys,
  createInitialLayout,
} from "../usePlotlyLayout";

function createFigure(layoutOverrides: Partial<Plotly.Layout> = {}): Figure {
  return {
    data: [],
    layout: { ...layoutOverrides } as Plotly.Layout,
    frames: null,
  };
}

describe("createInitialLayout", () => {
  it("sets defaults and merges figure layout", () => {
    const figure = createFigure({ title: { text: "Test" }, dragmode: "zoom" });
    const result = createInitialLayout(figure);

    expect(result.autosize).toBe(true);
    expect(result.height).toBe(540);
    expect(result.dragmode).toBe("zoom"); // figure overrides default
    expect(result.title).toEqual({ text: "Test" });
  });

  it("disables autosize when width is specified", () => {
    const result = createInitialLayout(createFigure({ width: 800 }));
    expect(result.autosize).toBe(false);
  });
});

describe("computeLayoutOnFigureChange", () => {
  it("preserves only dragmode/xaxis/yaxis from previous layout (#7964)", () => {
    const nextFigure = createFigure({ title: { text: "New" } });
    const prevLayout: Partial<Plotly.Layout> = {
      dragmode: "zoom",
      xaxis: { range: [0, 10] },
      yaxis: { range: [0, 100] },
      shapes: [{ type: "rect", x0: 0, x1: 1, y0: 0, y1: 1 }],
      annotations: [{ text: "Old", x: 0, y: 0 }],
    };

    const result = computeLayoutOnFigureChange(nextFigure, prevLayout);

    // Preserved from prev
    expect(result.dragmode).toBe("zoom");
    expect(result.xaxis).toEqual({ range: [0, 10] });
    expect(result.yaxis).toEqual({ range: [0, 100] });
    // From new figure
    expect(result.title).toEqual({ text: "New" });
    // NOT preserved (the bug fix)
    expect(result.shapes).toBeUndefined();
    expect(result.annotations).toBeUndefined();
  });

  it("uses shapes from new figure, not previous layout", () => {
    const nextFigure = createFigure({
      shapes: [{ type: "circle", x0: 0, x1: 1, y0: 0, y1: 1 }],
    });
    const prevLayout: Partial<Plotly.Layout> = {
      shapes: [{ type: "rect", x0: 0, x1: 1, y0: 0, y1: 1 }],
    };

    const result = computeLayoutOnFigureChange(nextFigure, prevLayout);

    expect(result.shapes).toHaveLength(1);
    expect(result.shapes?.[0].type).toBe("circle");
  });
});

describe("computeOmitKeys", () => {
  it("omits user-interaction keys unless they changed in figure", () => {
    const unchanged = computeOmitKeys({}, {});
    expect([...unchanged]).toEqual(
      expect.arrayContaining(["autosize", "dragmode", "xaxis", "yaxis"]),
    );

    const changed = computeOmitKeys(
      { dragmode: "zoom", xaxis: { range: [0, 10] } },
      { dragmode: "select", xaxis: { range: [0, 5] } },
    );
    expect(changed.has("dragmode")).toBe(false);
    expect(changed.has("xaxis")).toBe(false);
    expect(changed.has("autosize")).toBe(true);
  });
});

describe("computeLayoutUpdate", () => {
  it("merges figure layout while respecting omit keys", () => {
    // dragmode unchanged in figure -> preserve prev layout's dragmode
    const result1 = computeLayoutUpdate(
      { dragmode: "pan", title: { text: "New" } },
      { dragmode: "pan" },
      { dragmode: "zoom", height: 400 },
    );
    expect(result1.dragmode).toBe("zoom");
    expect(result1.title).toEqual({ text: "New" });
    expect(result1.height).toBe(400);

    // dragmode changed in figure -> use figure's dragmode
    const result2 = computeLayoutUpdate(
      { dragmode: "pan" },
      { dragmode: "select" },
      { dragmode: "zoom" },
    );
    expect(result2.dragmode).toBe("pan");
  });
});
