/* Copyright 2026 Marimo. All rights reserved. */

import { pick } from "lodash-es";
import type * as Plotly from "plotly.js";

import { createParser, type PlotlyTemplateParser } from "./parse-from-template";

type AxisName = string;
type AxisDatum = unknown;

const SUNBURST_DATA_KEYS: (keyof Plotly.SunburstPlotDatum)[] = [
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

const LINE_CLICK_TRACE_TYPES = new Set(["scatter", "scattergl"]);

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

type PointWithFullData = Plotly.PlotDatum & {
  pointNumbers?: number[];
  fullData?: {
    type?: string;
    mode?: string;
    x?: unknown[];
    y?: unknown[];
    hovertemplate?: string | string[];
  };
};

interface TraceSource {
  type?: string;
  mode?: string;
  x?: unknown[];
  y?: unknown[];
  hovertemplate?: string | string[];
}

export type ModeBarButton = NonNullable<
  Plotly.Config["modeBarButtonsToAdd"]
>[number];

function coalesceField<T>(
  primary: T | undefined,
  fallback: T | undefined,
): T | undefined {
  return primary ?? fallback;
}

function getTraceSource(point: Plotly.PlotDatum): TraceSource {
  const withFullData = point as PointWithFullData;
  const data = (point.data ?? {}) as TraceSource;
  const fullData = (withFullData.fullData ?? {}) as TraceSource;

  // Plotly click payloads sometimes include partial `data` plus richer `fullData`.
  // Merge field-by-field so we don't lose type/mode/x/y metadata for pure lines.
  return {
    type: coalesceField(data.type, fullData.type),
    mode: coalesceField(data.mode, fullData.mode),
    x: coalesceField(data.x, fullData.x),
    y: coalesceField(data.y, fullData.y),
    hovertemplate: coalesceField(data.hovertemplate, fullData.hovertemplate),
  };
}

function asFiniteNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : undefined;
}

function getPointIndex(point: Plotly.PlotDatum): number | undefined {
  const pointIndex = asFiniteNumber(point.pointIndex);
  if (pointIndex !== undefined) {
    return pointIndex;
  }

  const pointNumber = asFiniteNumber(point.pointNumber);
  if (pointNumber !== undefined) {
    return pointNumber;
  }

  const pointNumbers = (point as PointWithFullData).pointNumbers;
  if (!Array.isArray(pointNumbers)) {
    return undefined;
  }

  return pointNumbers.map(asFiniteNumber).find((n) => n !== undefined);
}

function isLinePoint(point: Plotly.PlotDatum): boolean {
  const trace = getTraceSource(point);
  if (!LINE_CLICK_TRACE_TYPES.has(String(trace.type))) {
    return false;
  }

  const mode = trace.mode;
  if (typeof mode !== "string") {
    // Some Plotly click payloads omit mode on point.data, especially with
    // line traces; treat scatter/scattergl as line-like in this case.
    return true;
  }

  return mode.split("+").includes("lines");
}

function isPureLineMode(mode: unknown): boolean {
  if (typeof mode !== "string") {
    return false;
  }
  const parts = mode.split("+");
  return parts.includes("lines") && !parts.includes("markers");
}

export function hasPureLineTrace(
  data: readonly Plotly.Data[] | undefined,
): boolean {
  if (!data) {
    return false;
  }

  return data.some((trace) => {
    const traceType = (trace as { type?: unknown }).type;
    const isScatterLike =
      traceType === undefined || LINE_CLICK_TRACE_TYPES.has(String(traceType));
    if (!isScatterLike) {
      return false;
    }
    return isPureLineMode((trace as { mode?: unknown }).mode);
  });
}

function createDragmodeButton(
  name: string,
  title: string,
  svg: string,
  dragmode: Plotly.Layout["dragmode"],
  setDragmode: (dragmode: Plotly.Layout["dragmode"]) => void,
): ModeBarButton {
  return {
    name,
    title,
    icon: { svg },
    click: () => setDragmode(dragmode),
  };
}

export function lineSelectionButtons(
  setDragmode: (dragmode: Plotly.Layout["dragmode"]) => void,
): ModeBarButton[] {
  return [
    createDragmodeButton(
      "line-box-select",
      "Box select",
      `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="4" y="4" width="16" height="16" stroke-dasharray="2 2" />
      </svg>`,
      "select",
      setDragmode,
    ),
    createDragmodeButton(
      "line-lasso-select",
      "Lasso select",
      `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M6 8c0-2.2 2.2-4 5-4s5 1.8 5 4-2.2 4-5 4-5 1.8-5 4 2.2 4 5 4" />
        <circle cx="17.5" cy="16.5" r="1.5" />
      </svg>`,
      "lasso",
      setDragmode,
    ),
  ];
}

export function mergeModeBarButtonsToAdd(
  defaults: readonly ModeBarButton[],
  userButtons: readonly ModeBarButton[] | undefined,
): ModeBarButton[] {
  const merged: ModeBarButton[] = [];
  const seenStrings = new Set<string>();

  const pushButton = (button: ModeBarButton) => {
    if (typeof button === "string") {
      if (seenStrings.has(button)) {
        return;
      }
      seenStrings.add(button);
      merged.push(button);
      return;
    }
    merged.push(button);
  };

  defaults.forEach(pushButton);
  userButtons?.forEach(pushButton);
  return merged;
}

export function shouldHandleClickSelection(
  points: readonly Plotly.PlotDatum[],
): boolean {
  return points.some((point) => {
    const type = getTraceSource(point).type;
    return (
      type === "bar" ||
      type === "heatmap" ||
      type === "histogram" ||
      type === "waterfall" ||
      isLinePoint(point)
    );
  });
}

export function extractIndices(points: readonly Plotly.PlotDatum[]): number[] {
  return points
    .map(getPointIndex)
    .filter((pointIndex): pointIndex is number => pointIndex !== undefined);
}

function getIndexedValue(series: unknown, index: number): unknown {
  if (Array.isArray(series) || ArrayBuffer.isView(series)) {
    return (series as ArrayLike<unknown>)[index];
  }
  if (typeof series === "object" && series !== null && "length" in series) {
    const maybeLength = Number(
      (series as { length?: unknown }).length ?? Number.NaN,
    );
    if (Number.isFinite(maybeLength) && index >= 0 && index < maybeLength) {
      return (series as Record<number, unknown>)[index];
    }
  }
  return undefined;
}

function withInferredXY(
  point: Plotly.PlotDatum,
  fields: Record<AxisName, AxisDatum>,
): Record<AxisName, AxisDatum> {
  // For some pure-line clicks Plotly provides index metadata but omits x/y.
  // Recover x/y from trace arrays so Python gets a stable payload.
  if (fields.x !== undefined && fields.y !== undefined) {
    return fields;
  }

  const pointIndex = getPointIndex(point);
  if (pointIndex === undefined) {
    return fields;
  }

  const nextFields: Record<AxisName, AxisDatum> = { ...fields };
  if (nextFields.pointIndex === undefined) {
    nextFields.pointIndex = pointIndex;
  }

  const trace = getTraceSource(point);
  if (nextFields.x === undefined) {
    const inferredX = getIndexedValue(trace.x, pointIndex);
    if (inferredX !== undefined) {
      nextFields.x = inferredX;
    }
  }
  if (nextFields.y === undefined) {
    const inferredY = getIndexedValue(trace.y, pointIndex);
    if (inferredY !== undefined) {
      nextFields.y = inferredY;
    }
  }

  return nextFields;
}

export function extractPoints(
  points: readonly Plotly.PlotDatum[],
): Record<AxisName, AxisDatum>[] {
  let parser: PlotlyTemplateParser | undefined;

  return points.map((point) => {
    const standardPointFields = withInferredXY(
      point,
      pick(point, STANDARD_POINT_KEYS),
    );

    const trace = getTraceSource(point);

    // Get the first hovertemplate
    const hovertemplate = Array.isArray(trace.hovertemplate)
      ? trace.hovertemplate[0]
      : trace.hovertemplate;

    // For chart types with standard point keys (e.g. heatmaps),
    // or when there's no hovertemplate, pick keys directly from the point.
    if (!hovertemplate || trace.type === "heatmap") {
      return standardPointFields;
    }

    parser = parser
      ? parser.update(hovertemplate)
      : createParser(hovertemplate);
    return {
      ...standardPointFields,
      ...parser.parse(point),
    };
  });
}

export function extractSunburstPoints(
  points: readonly Plotly.PlotDatum[],
): Record<string, unknown>[] {
  return points.map((point) => pick(point, SUNBURST_DATA_KEYS));
}

export const extractTreemapPoints = extractSunburstPoints;
