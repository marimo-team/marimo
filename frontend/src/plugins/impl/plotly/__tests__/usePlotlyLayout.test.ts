/* Copyright 2026 Marimo. All rights reserved. */

import type * as Plotly from "plotly.js";
import { describe, expect, it } from "vitest";
import type { Figure } from "../Plot";
import {
  computeLayoutOnFigureChange,
  computeLayoutUpdate,
  computeOmitKeys,
  createInitialLayout,
  hasCompatibleTraces,
} from "../usePlotlyLayout";

function createFigure(
  layoutOverrides: Partial<Plotly.Layout> = {},
  data: Plotly.Data[] = [],
): Figure {
  return {
    data,
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

describe("hasCompatibleTraces", () => {
  it("returns true for same trace types", () => {
    const a = createFigure({}, [{ type: "scatter" } as Plotly.Data]);
    const b = createFigure({}, [{ type: "scatter" } as Plotly.Data]);
    expect(hasCompatibleTraces(a, b)).toBe(true);
  });

  it("returns true for default scatter types (undefined type)", () => {
    const a = createFigure({}, [{} as Plotly.Data]);
    const b = createFigure({}, [{ type: "scatter" } as Plotly.Data]);
    expect(hasCompatibleTraces(a, b)).toBe(true);
  });

  it("returns false for different trace types", () => {
    const a = createFigure({}, [{ type: "scatter" } as Plotly.Data]);
    const b = createFigure({}, [{ type: "histogram" } as Plotly.Data]);
    expect(hasCompatibleTraces(a, b)).toBe(false);
  });

  it("returns false for different number of traces", () => {
    const a = createFigure({}, [{ type: "scatter" } as Plotly.Data]);
    const b = createFigure({}, [
      { type: "scatter" } as Plotly.Data,
      { type: "scatter" } as Plotly.Data,
    ]);
    expect(hasCompatibleTraces(a, b)).toBe(false);
  });

  it("returns true for empty data arrays", () => {
    const a = createFigure({}, []);
    const b = createFigure({}, []);
    expect(hasCompatibleTraces(a, b)).toBe(true);
  });
});

describe("computeLayoutOnFigureChange", () => {
  it("preserves only dragmode/xaxis/yaxis from previous layout for compatible traces (#7964)", () => {
    const scatterData = [{ type: "scatter" } as Plotly.Data];
    const prevFigure = createFigure({}, scatterData);
    const nextFigure = createFigure({ title: { text: "New" } }, scatterData);
    const prevLayout: Partial<Plotly.Layout> = {
      dragmode: "zoom",
      xaxis: { range: [0, 10] },
      yaxis: { range: [0, 100] },
      shapes: [{ type: "rect", x0: 0, x1: 1, y0: 0, y1: 1 }],
      annotations: [{ text: "Old", x: 0, y: 0 }],
    };

    const result = computeLayoutOnFigureChange(
      nextFigure,
      prevFigure,
      prevLayout,
    );

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

  it("resets axis settings when trace types change (#5898)", () => {
    const prevFigure = createFigure({}, [{ type: "histogram" } as Plotly.Data]);
    const nextFigure = createFigure({ title: { text: "Bar" } }, [
      { type: "bar" } as Plotly.Data,
    ]);
    const prevLayout: Partial<Plotly.Layout> = {
      dragmode: "zoom",
      xaxis: { range: [-3, 3] },
      yaxis: { range: [0, 200] },
    };

    const result = computeLayoutOnFigureChange(
      nextFigure,
      prevFigure,
      prevLayout,
    );

    // Dragmode is still preserved
    expect(result.dragmode).toBe("zoom");
    // Axis settings are NOT preserved — they come from the new figure's layout
    expect(result.xaxis).toBeUndefined();
    expect(result.yaxis).toBeUndefined();
    // New figure's layout is applied
    expect(result.title).toEqual({ text: "Bar" });
  });

  it("preserves nextFigure dragmode when prevLayout has no dragmode", () => {
    const prevFigure = createFigure({}, [{ type: "histogram" } as Plotly.Data]);
    const nextFigure = createFigure({ dragmode: "lasso" }, [
      { type: "bar" } as Plotly.Data,
    ]);
    const prevLayout: Partial<Plotly.Layout> = {
      xaxis: { range: [0, 10] },
    };

    const result = computeLayoutOnFigureChange(
      nextFigure,
      prevFigure,
      prevLayout,
    );

    // nextFigure.layout.dragmode should be preserved via base, not overwritten
    expect(result.dragmode).toBe("lasso");
    // Axis settings are NOT preserved for incompatible traces
    expect(result.xaxis).toBeUndefined();
    expect(result.yaxis).toBeUndefined();
  });

  it("uses shapes from new figure, not previous layout", () => {
    const nextFigure = createFigure({
      shapes: [{ type: "circle", x0: 0, x1: 1, y0: 0, y1: 1 }],
    });
    const prevFigure = createFigure({});
    const prevLayout: Partial<Plotly.Layout> = {
      shapes: [{ type: "rect", x0: 0, x1: 1, y0: 0, y1: 1 }],
    };

    const result = computeLayoutOnFigureChange(
      nextFigure,
      prevFigure,
      prevLayout,
    );

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
