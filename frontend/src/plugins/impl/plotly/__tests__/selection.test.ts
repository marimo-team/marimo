/* Copyright 2026 Marimo. All rights reserved. */

import type * as Plotly from "plotly.js";
import { describe, expect, it } from "vitest";
import {
  extractClickSelection,
  extractIndices,
  extractPoints,
} from "../selection";

interface PlotlyPointInput {
  data: {
    type: string;
    hovertemplate?: string | string[];
  };
  [key: string]: unknown;
}

function makePoint(point: PlotlyPointInput): Plotly.PlotDatum {
  return point as unknown as Plotly.PlotDatum;
}

function makeClickEvent(
  points: Plotly.PlotDatum[],
): Readonly<Plotly.PlotMouseEvent> {
  return { points } as unknown as Readonly<Plotly.PlotMouseEvent>;
}

describe("extractIndices", () => {
  it("prefers pointIndex and falls back to pointNumber", () => {
    const points = [
      makePoint({
        pointIndex: 2,
        pointNumber: 99,
        data: { type: "scatter" },
      }),
      makePoint({
        pointNumber: 4,
        data: { type: "scattergl" },
      }),
      makePoint({
        data: { type: "heatmap" },
      }),
    ];

    expect(extractIndices(points)).toEqual([2, 4]);
  });
});

describe("extractPoints", () => {
  it("extracts parsed scatter payload fields from the hovertemplate", () => {
    const points = [
      makePoint({
        x: 3,
        y: 7,
        curveNumber: 0,
        pointIndex: 1,
        customdata: ["B"],
        data: {
          type: "scatter",
          hovertemplate:
            "label=%{customdata[0]}<br>x=%{x}<br>y=%{y}<extra></extra>",
        },
      }),
    ];

    expect(extractPoints(points)).toEqual([
      {
        x: 3,
        y: 7,
        curveNumber: 0,
        pointIndex: 1,
        label: "B",
      },
    ]);
  });

  it("keeps standard heatmap keys without hovertemplate parsing", () => {
    const points = [
      makePoint({
        x: "B",
        y: "Row 2",
        z: 6,
        curveNumber: 0,
        pointIndex: 5,
        data: { type: "heatmap", hovertemplate: "ignored=%{z}" },
      }),
    ];

    expect(extractPoints(points)).toEqual([
      {
        x: "B",
        y: "Row 2",
        z: 6,
        curveNumber: 0,
        pointIndex: 5,
      },
    ]);
  });
});

describe("extractClickSelection", () => {
  it("returns undefined for unsupported trace types", () => {
    const event = makeClickEvent([
      makePoint({
        x: "A",
        y: 10,
        pointIndex: 0,
        data: { type: "bar" },
      }),
    ]);

    expect(extractClickSelection(event)).toBeUndefined();
  });

  it("filters unsupported points and preserves supported click payloads", () => {
    const event = makeClickEvent([
      makePoint({
        x: "ignore",
        y: 1,
        pointIndex: 0,
        data: { type: "bar" },
      }),
      makePoint({
        x: 2,
        y: 5,
        curveNumber: 1,
        pointIndex: 3,
        customdata: ["P2"],
        data: {
          type: "scatter",
          hovertemplate:
            "label=%{customdata[0]}<br>x=%{x}<br>y=%{y}<extra></extra>",
        },
      }),
      makePoint({
        x: 4,
        y: 12,
        curveNumber: 2,
        pointNumber: 5,
        customdata: ["Q4"],
        data: {
          type: "scattergl",
          hovertemplate:
            "label=%{customdata[0]}<br>x=%{x}<br>value=%{y}<extra></extra>",
        },
      }),
    ]);

    expect(extractClickSelection(event)).toEqual({
      selections: [],
      range: undefined,
      indices: [3, 5],
      points: [
        {
          x: 2,
          y: 5,
          curveNumber: 1,
          pointIndex: 3,
          label: "P2",
        },
        {
          x: 4,
          y: 12,
          curveNumber: 2,
          pointNumber: 5,
          value: 12,
          label: "Q4",
        },
      ],
    });
  });

  it("preserves histogram pointNumbers for backend row extraction", () => {
    const event = makeClickEvent([
      makePoint({
        x: 8,
        y: 2,
        curveNumber: 0,
        pointNumber: 3,
        pointNumbers: [6, 7],
        data: { type: "histogram" },
      }),
    ]);

    expect(extractClickSelection(event)).toEqual({
      selections: [],
      range: undefined,
      indices: [3],
      points: [
        {
          x: 8,
          y: 2,
          curveNumber: 0,
          pointNumber: 3,
          pointNumbers: [6, 7],
        },
      ],
    });
  });

  it("preserves standard heatmap click payloads", () => {
    const event = makeClickEvent([
      makePoint({
        x: "C",
        y: "Row 3",
        z: 11,
        curveNumber: 0,
        pointIndex: 10,
        data: { type: "heatmap" },
      }),
    ]);

    expect(extractClickSelection(event)).toEqual({
      selections: [],
      range: undefined,
      indices: [10],
      points: [
        {
          x: "C",
          y: "Row 3",
          z: 11,
          curveNumber: 0,
          pointIndex: 10,
        },
      ],
    });
  });
});
