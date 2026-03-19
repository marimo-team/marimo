/* Copyright 2026 Marimo. All rights reserved. */

import { pick } from "lodash-es";
import type * as Plotly from "plotly.js";
import { Arrays } from "@/utils/arrays";
import { createParser, type PlotlyTemplateParser } from "./parse-from-template";

type AxisName = string;
type AxisDatum = unknown;

export interface PlotlyClickSelection {
  points: Record<AxisName, AxisDatum>[] | Plotly.PlotDatum[];
  indices: number[];
  range: undefined;
  selections: unknown[];
}

const CLICK_SELECTABLE_TRACE_TYPES = new Set([
  "heatmap",
  "histogram",
  "scatter",
  "scattergl",
]);

const STANDARD_POINT_KEYS: string[] = [
  "x",
  "y",
  "z",
  "lat",
  "lon",
  "curveNumber",
  "pointNumber",
  "pointNumbers",
  "pointIndex",
] as const;

function getPointIndex(point: Plotly.PlotDatum): number | undefined {
  if (typeof point.pointIndex === "number") {
    return point.pointIndex;
  }

  if (typeof point.pointNumber === "number") {
    return point.pointNumber;
  }

  return undefined;
}

function isClickSelectablePoint(point: Plotly.PlotDatum): boolean {
  const traceType = point.data?.type;
  return typeof traceType === "string"
    ? CLICK_SELECTABLE_TRACE_TYPES.has(traceType)
    : false;
}

export function extractIndices(points: Plotly.PlotDatum[]): number[] {
  return points.flatMap((point) => {
    const index = getPointIndex(point);
    return typeof index === "number" ? [index] : [];
  });
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
    const standardPointFields = pick(point, STANDARD_POINT_KEYS);

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

export function extractClickSelection(
  evt: Readonly<Plotly.PlotMouseEvent>,
): PlotlyClickSelection | undefined {
  if (!evt.points?.length) {
    return undefined;
  }

  const points = evt.points.filter(isClickSelectablePoint);
  if (points.length === 0) {
    return undefined;
  }

  return {
    selections: Arrays.EMPTY,
    points: extractPoints(points),
    indices: extractIndices(points),
    range: undefined,
  };
}
