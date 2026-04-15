/* Copyright 2026 Marimo. All rights reserved. */

import type * as Plotly from "plotly.js";
import { describe, expect, it, vi } from "vitest";
import {
  extractIndices,
  extractPoints,
  hasAreaTrace,
  hasPureLineTrace,
  lineSelectionButtons,
  type ModeBarButton,
  mergeModeBarButtonsToAdd,
  shouldHandleClickSelection,
} from "../selection";

function createTrace(trace: Partial<Plotly.PlotData>): Plotly.Data {
  return trace as unknown as Plotly.Data;
}

function createPlotDatum<T extends object>(overrides: T): Plotly.PlotDatum & T {
  return overrides as unknown as Plotly.PlotDatum & T;
}

describe("hasPureLineTrace", () => {
  it("detects scatter and scattergl traces that are pure lines", () => {
    expect(
      hasPureLineTrace([
        createTrace({ type: "scatter", mode: "lines" }),
        createTrace({ type: "scattergl", mode: "text+lines" }),
      ]),
    ).toBe(true);
  });

  it("ignores non-line and marker traces", () => {
    expect(
      hasPureLineTrace([
        createTrace({ type: "scatter", mode: "markers" }),
        createTrace({ type: "scatter", mode: "lines+markers" }),
        createTrace({ type: "bar" }),
      ]),
    ).toBe(false);
  });
});

describe("lineSelectionButtons", () => {
  it("creates dragmode buttons that update dragmode", () => {
    const setDragmode = vi.fn();
    const buttons = lineSelectionButtons(setDragmode);

    expect(buttons).toHaveLength(2);
    expect(
      buttons.map((button) =>
        typeof button === "string" ? button : button.name,
      ),
    ).toEqual(["line-box-select", "line-lasso-select"]);

    const graphDiv = document.createElement(
      "div",
    ) as unknown as Plotly.PlotlyHTMLElement;
    const clickEvent = new MouseEvent("click");

    (buttons[0] as Exclude<ModeBarButton, string>).click(graphDiv, clickEvent);
    (buttons[1] as Exclude<ModeBarButton, string>).click(graphDiv, clickEvent);

    expect(setDragmode).toHaveBeenNthCalledWith(1, "select");
    expect(setDragmode).toHaveBeenNthCalledWith(2, "lasso");
  });
});

describe("mergeModeBarButtonsToAdd", () => {
  it("deduplicates string buttons while preserving custom buttons", () => {
    const customButton = {
      name: "custom",
      title: "Custom",
      icon: { svg: "<svg />" },
      click: vi.fn(),
    } satisfies Exclude<ModeBarButton, string>;

    expect(
      mergeModeBarButtonsToAdd(
        ["zoom2d", "lasso2d"],
        ["lasso2d", customButton, "zoom2d"],
      ),
    ).toEqual(["zoom2d", "lasso2d", customButton]);
  });
});

describe("shouldHandleClickSelection", () => {
  it("accepts bar clicks", () => {
    const barPoint = createPlotDatum({
      data: { type: "bar" },
    });

    expect(shouldHandleClickSelection([barPoint])).toBe(true);
  });

  it("accepts heatmap clicks", () => {
    const heatmapPoint = createPlotDatum({
      data: { type: "heatmap" },
    });

    expect(shouldHandleClickSelection([heatmapPoint])).toBe(true);
  });

  it("accepts box clicks", () => {
    const boxPoint = createPlotDatum({
      data: { type: "box" },
    });

    expect(shouldHandleClickSelection([boxPoint])).toBe(true);
  });

  it("accepts violin clicks", () => {
    const violinPoint = createPlotDatum({
      data: { type: "violin" },
    });

    expect(shouldHandleClickSelection([violinPoint])).toBe(true);
  });

  it("accepts histogram clicks", () => {
    const histogramPoint = createPlotDatum({
      data: { type: "histogram" },
    });

    expect(shouldHandleClickSelection([histogramPoint])).toBe(true);
  });

  it("accepts scatter clicks when Plotly omits mode", () => {
    const linePoint = createPlotDatum({
      data: { type: "scatter" },
    });

    expect(shouldHandleClickSelection([linePoint])).toBe(true);
  });

  it("accepts funnel clicks", () => {
    const funnelPoint = createPlotDatum({
      data: { type: "funnel" },
    });

    expect(shouldHandleClickSelection([funnelPoint])).toBe(true);
  });

  it("accepts funnelarea clicks", () => {
    const funnelAreaPoint = createPlotDatum({
      data: { type: "funnelarea" },
    });

    expect(shouldHandleClickSelection([funnelAreaPoint])).toBe(true);
  });

  it("accepts waterfall clicks", () => {
    const waterfallPoint = createPlotDatum({
      data: { type: "waterfall" },
    });

    expect(shouldHandleClickSelection([waterfallPoint])).toBe(true);
  });

  it("rejects non-line scatter marker clicks", () => {
    const markerPoint = createPlotDatum({
      data: { type: "scatter", mode: "markers" },
    });

    expect(shouldHandleClickSelection([markerPoint])).toBe(false);
  });
});

describe("extractIndices", () => {
  it("prefers pointIndex and falls back to pointNumber and pointNumbers", () => {
    const points = [
      createPlotDatum({ pointIndex: 2 }),
      createPlotDatum({ pointNumber: 5 }),
      createPlotDatum({ pointNumbers: [Number.NaN, 8] }),
      createPlotDatum({ pointNumbers: [Infinity] }),
    ];

    expect(extractIndices(points)).toEqual([2, 5, 8]);
  });
});

describe("extractPoints", () => {
  it("infers missing x/y from trace data for line clicks", () => {
    const point = createPlotDatum({
      pointNumber: 1,
      data: { type: "scatter" },
      fullData: {
        type: "scatter",
        mode: "lines",
        x: new Float64Array([10, 20, 30]),
        y: [100, 200, 300],
      },
    });

    expect(extractPoints([point])).toEqual([
      { pointNumber: 1, pointIndex: 1, x: 20, y: 200 },
    ]);
  });

  it("parses hovertemplate values while keeping inferred point fields", () => {
    const point = createPlotDatum({
      pointIndex: 0,
      customdata: ["Mustang", "USA"],
      fullData: {
        type: "scatter",
        mode: "lines",
        x: ["300"],
        y: ["30"],
        hovertemplate:
          "Name=%{customdata[0]}<br>Origin=%{customdata[1]}<extra></extra>",
      },
    });

    expect(extractPoints([point])).toEqual([
      {
        pointIndex: 0,
        x: "300",
        y: "30",
        Name: "Mustang",
        Origin: "USA",
      },
    ]);
  });

  it("returns only standard fields for heatmaps", () => {
    const point = createPlotDatum({
      x: 1,
      y: 2,
      z: 3,
      text: "ignored",
      data: {
        type: "heatmap",
        hovertemplate: "Label=%{text}<extra></extra>",
      },
    });

    expect(extractPoints([point])).toEqual([{ x: 1, y: 2, z: 3 }]);
  });

  it("returns funnel-specific fields for funnel traces", () => {
    const point = createPlotDatum({
      x: 1000,
      y: "Visit",
      label: "Visit",
      value: 1000,
      percentInitial: 1.0,
      percentPrevious: 1.0,
      percentTotal: 1.0,
      curveNumber: 0,
      pointIndex: 0,
      pointNumber: 0,
      data: { type: "funnel" },
    });

    expect(extractPoints([point])).toEqual([
      {
        x: 1000,
        y: "Visit",
        label: "Visit",
        value: 1000,
        percentInitial: 1.0,
        percentPrevious: 1.0,
        percentTotal: 1.0,
        curveNumber: 0,
        pointIndex: 0,
        pointNumber: 0,
      },
    ]);
  });

  it("returns funnelarea-specific fields without x/y for funnelarea traces", () => {
    const point = createPlotDatum({
      label: "Stage A",
      value: 500,
      percentInitial: 0.5,
      percentPrevious: 0.8,
      percentTotal: 0.5,
      curveNumber: 0,
      pointNumber: 1,
      x: 99,
      y: 99,
      data: { type: "funnelarea" },
    });

    expect(extractPoints([point])).toEqual([
      {
        label: "Stage A",
        value: 500,
        percentInitial: 0.5,
        percentPrevious: 0.8,
        percentTotal: 0.5,
        curveNumber: 0,
        pointNumber: 1,
      },
    ]);
  });

  it("returns x/y/pointIndex for waterfall clicks", () => {
    const point = createPlotDatum({
      x: "Revenue",
      y: 400,
      pointIndex: 1,
      curveNumber: 0,
      data: { type: "waterfall" },
    });

    expect(extractPoints([point])).toEqual([
      { x: "Revenue", y: 400, pointIndex: 1, curveNumber: 0 },
    ]);
  });
});

describe("hasAreaTrace", () => {
  it("detects scatter trace with tozeroy fill", () => {
    expect(
      hasAreaTrace([createTrace({ type: "scatter", fill: "tozeroy" })]),
    ).toBe(true);
  });

  it("detects scatter trace with tonexty fill", () => {
    expect(
      hasAreaTrace([createTrace({ type: "scatter", fill: "tonexty" })]),
    ).toBe(true);
  });

  it("detects scatter trace with stackgroup (px.area pattern)", () => {
    expect(
      hasAreaTrace([
        createTrace({ type: "scatter", mode: "lines", stackgroup: "one" }),
      ]),
    ).toBe(true);
  });

  it("detects area traces with mode=none (fill-only, no visible line)", () => {
    expect(
      hasAreaTrace([
        createTrace({ type: "scatter", fill: "tozeroy", mode: "none" }),
      ]),
    ).toBe(true);
  });

  it("ignores scatter traces with no fill and no stackgroup", () => {
    expect(
      hasAreaTrace([
        createTrace({ type: "scatter", mode: "lines" }),
        createTrace({ type: "scatter", mode: "markers" }),
      ]),
    ).toBe(false);
  });

  it("ignores scatter traces with fill=none", () => {
    expect(hasAreaTrace([createTrace({ type: "scatter", fill: "none" })])).toBe(
      false,
    );
  });

  it("ignores scatter traces with fill=empty string", () => {
    expect(
      hasAreaTrace([createTrace({ type: "scatter", fill: "" as "none" })]),
    ).toBe(false);
  });

  it("ignores non-scatter traces", () => {
    expect(
      hasAreaTrace([
        createTrace({ type: "bar" }),
        createTrace({ type: "heatmap" }),
      ]),
    ).toBe(false);
  });

  it("returns false for undefined data", () => {
    expect(hasAreaTrace(undefined)).toBe(false);
  });
});
