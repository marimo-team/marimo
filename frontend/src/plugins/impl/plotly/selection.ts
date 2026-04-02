/* Copyright 2026 Marimo. All rights reserved. */

import type * as Plotly from "plotly.js";
import { Objects } from "@/utils/objects";
import { createParser, type PlotlyTemplateParser } from "./parse-from-template";

type AxisName = string;
type AxisDatum = unknown;

export const SUNBURST_DATA_KEYS: (keyof Plotly.SunburstPlotDatum)[] = [
  "color",
  "curveNumber",
  "entry",
  "hovertext",
  "id",
  "label",
  "parent",
  "percentEntry",
  "percentParent",
  "percentRoot",
  "pointNumber",
  "root",
  "value",
] as const;

export const TREE_MAP_DATA_KEYS = SUNBURST_DATA_KEYS;

// Chart types where Plotly's box/lasso selection does not produce per-point
// payloads, so we rely on the click event to capture data instead.
export const CLICK_SELECTABLE_TRACE_TYPES = new Set(["heatmap", "bar"]);

export const STANDARD_POINT_KEYS: string[] = [
  "x",
  "y",
  "z",
  "lat",
  "lon",
  "curveNumber",
  "pointNumber",
  "pointNumbers",
  "pointIndex",
];

function getPointIndex(point: Plotly.PlotDatum): number | undefined {
  return point.pointIndex ?? point.pointNumber;
}

export function extractIndices(points: Plotly.PlotDatum[]): number[] {
  const indices: number[] = [];
  for (const point of points) {
    const index = getPointIndex(point);
    if (index !== undefined) {
      indices.push(index);
    }
  }
  return indices;
}

/**
 * This is a hack to extract the points with their original keys,
 * instead of the ones that Plotly uses internally,
 * by using the hovertemplate.
 */
export function extractPoints(
  points: Plotly.PlotDatum[],
): Record<AxisName, AxisDatum>[] {
  if (!points) {
    return [];
  }

  let parser: PlotlyTemplateParser | undefined;

  return points.map((point) => {
    const standardPointFields = Objects.pick(point, STANDARD_POINT_KEYS);

    // Get the first hovertemplate
    const hovertemplate = Array.isArray(point.data.hovertemplate)
      ? point.data.hovertemplate[0]
      : point.data.hovertemplate;

    // For chart types with standard point keys (e.g. heatmaps),
    // or when there's no hovertemplate, pick keys directly from the point.
    if (!hovertemplate || point.data?.type === "heatmap") {
      return standardPointFields;
    }

    // Update or create a parser
    parser = parser
      ? parser.update(hovertemplate)
      : createParser(hovertemplate);
    return {
      ...standardPointFields,
      ...parser.parse(point),
    };
  });
}
