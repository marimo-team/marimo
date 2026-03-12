/* Copyright 2026 Marimo. All rights reserved. */

import type * as Plotly from "plotly.js";
import { z } from "zod";
import type { IPlugin, IPluginProps, Setter } from "@/plugins/types";
import { Logger } from "@/utils/Logger";
import type { Figure } from "./Plot";

import "./plotly.css";
import "./mapbox.css";
import { pick, set } from "lodash-es";
import { type JSX, lazy, memo, useMemo } from "react";
import useEvent from "react-use-event-hook";
import { useDeepCompareMemoize } from "@/hooks/useDeepCompareMemoize";
import { useScript } from "@/hooks/useScript";
import { Arrays } from "@/utils/arrays";
import { createParser, type PlotlyTemplateParser } from "./parse-from-template";
import { usePlotlyLayout } from "./usePlotlyLayout";

interface Data {
  figure: Figure;
  config: Partial<Plotly.Config>;
}

type AxisName = string;
type AxisDatum = unknown;

type T =
  | {
      points?: Record<AxisName, AxisDatum>[] | Plotly.PlotDatum[];
      indices?: number[];
      range?: {
        x?: number[];
        y?: number[];
      };
      lasso?: {
        x?: unknown[];
        y?: unknown[];
      };
      // These are kept in the state to persist selections across re-renders
      // on the frontend, but likely not used in the backend.
      selections?: unknown[];
      dragmode?: Plotly.Layout["dragmode"];
      xaxis?: Partial<Plotly.LayoutAxis>;
      yaxis?: Partial<Plotly.LayoutAxis>;
    }
  | undefined;

export class PlotlyPlugin implements IPlugin<T, Data> {
  tagName = "marimo-plotly";

  validator = z.object({
    figure: z
      .object({})
      .passthrough()
      .transform((spec) => spec as unknown as Figure),
    config: z.object({}).passthrough(),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <PlotlyComponent
        {...props.data}
        host={props.host}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface PlotlyPluginProps extends Data {
  value: T;
  setValue: Setter<T>;
  host: HTMLElement;
}

const LazyPlot = lazy(() =>
  import("./Plot").then((mod) => ({ default: mod.Plot })),
);

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
const TREE_MAP_DATA_KEYS = SUNBURST_DATA_KEYS;
const LINE_CLICK_TRACE_TYPES = new Set(["scatter", "scattergl"]);

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

type ModeBarButton = NonNullable<Plotly.Config["modeBarButtonsToAdd"]>[number];

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

function lineSelectionButtons(
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

function mergeModeBarButtonsToAdd(
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
  return points.some(
    (point) => getTraceSource(point).type === "heatmap" || isLinePoint(point),
  );
}

export function extractIndices(points: readonly Plotly.PlotDatum[]): number[] {
  return points
    .map(getPointIndex)
    .filter((pointIndex): pointIndex is number => pointIndex !== undefined);
}

export const PlotlyComponent = memo(
  ({ figure: originalFigure, value, setValue, config }: PlotlyPluginProps) => {
    // Used for rendering LaTeX. TODO: Serve this library from Marimo
    const scriptStatus = useScript(
      "https://cdn.jsdelivr.net/npm/mathjax-full@3.2.2/es5/tex-mml-svg.min.js",
    );
    const isScriptLoaded = scriptStatus === "ready";

    const { figure, layout, setLayout, handleReset } = usePlotlyLayout({
      originalFigure,
      initialValue: value,
      isScriptLoaded,
    });

    const handleResetWithClear = useEvent(() => {
      handleReset();
      setValue({});
    });
    const handleSetDragmode = useEvent(
      (dragmode: Plotly.Layout["dragmode"]) => {
        setLayout((prev) => ({ ...prev, dragmode }));
        setValue((prev) => ({ ...prev, dragmode }));
      },
    );

    const configMemo = useDeepCompareMemoize(config);
    const plotlyConfig = useMemo((): Partial<Plotly.Config> => {
      const hasPureLine = hasPureLineTrace(figure.data);
      const defaultButtons: ModeBarButton[] = [
        // Custom button to reset the state
        {
          name: "reset",
          title: "Reset state",
          icon: {
            svg: `
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-rotate-ccw">
                <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                <path d="M3 3v5h5" />
              </svg>`,
          },
          click: handleResetWithClear,
        },
      ];
      if (hasPureLine) {
        defaultButtons.push(...lineSelectionButtons(handleSetDragmode));
      }

      return {
        displaylogo: false,
        // Prioritize user's config
        ...configMemo,
        modeBarButtonsToAdd: mergeModeBarButtonsToAdd(
          defaultButtons,
          configMemo.modeBarButtonsToAdd as
            | readonly ModeBarButton[]
            | undefined,
        ),
      };
    }, [handleResetWithClear, handleSetDragmode, configMemo, figure.data]);

    return (
      <LazyPlot
        {...figure}
        layout={layout}
        onRelayout={(layoutUpdate) => {
          // Persist dragmode in the state to keep it across re-renders
          if ("dragmode" in layoutUpdate) {
            setValue((prev) => ({ ...prev, dragmode: layoutUpdate.dragmode }));
          }

          // Persist xaxis/yaxis changes in the state to keep it across re-renders
          if (
            Object.keys(layoutUpdate).some(
              (key) => key.includes("xaxis") || key.includes("yaxis"),
            )
          ) {
            // Axis changes are keypath updates, so need to use lodash.set
            // e.g. xaxis.range[0], xaxis.range[1], yaxis.range[0], yaxis.range[1]
            const obj: Partial<Plotly.Layout> = {};
            Object.entries(layoutUpdate).forEach(([key, value]) => {
              set(obj, key, value);
            });
            setValue((prev) => ({ ...prev, ...obj }));
          }
        }}
        onDeselect={useEvent(() => {
          setValue((prev) => {
            return {
              ...prev,
              selections: Arrays.EMPTY,
              points: Arrays.EMPTY,
              indices: Arrays.EMPTY,
              range: undefined,
              lasso: undefined,
            };
          });
        })}
        onTreemapClick={useEvent((evt: Readonly<Plotly.PlotMouseEvent>) => {
          if (!evt) {
            return;
          }

          setValue((prev) => ({
            ...prev,
            points: evt.points.map((point) => pick(point, TREE_MAP_DATA_KEYS)),
          }));
        })}
        onSunburstClick={useEvent((evt: Readonly<Plotly.PlotMouseEvent>) => {
          if (!evt) {
            return;
          }

          setValue((prev) => ({
            ...prev,
            points: evt.points.map((point) => pick(point, SUNBURST_DATA_KEYS)),
          }));
        })}
        config={plotlyConfig}
        onClick={useEvent((evt: Readonly<Plotly.PlotMouseEvent>) => {
          if (!evt) {
            return;
          }
          // Handle clicks for chart types where box/lasso selection
          // is limited or unavailable (e.g. heatmaps, pure line traces).
          if (!shouldHandleClickSelection(evt.points)) {
            return;
          }
          const extractedPoints = extractPoints(evt.points);
          const extractedIndices = extractIndices(evt.points);
          setValue((prev) => ({
            ...prev,
            selections: Arrays.EMPTY,
            range: undefined,
            lasso: undefined,
            points: extractedPoints,
            indices: extractedIndices,
          }));
        })}
        onSelected={useEvent((evt: Readonly<Plotly.PlotSelectionEvent>) => {
          if (!evt) {
            return;
          }

          setValue((prev) => ({
            ...prev,
            selections:
              "selections" in evt ? (evt.selections as unknown[]) : [],
            points: extractPoints(evt.points),
            indices: extractIndices(evt.points),
            range: evt.range,
            lasso:
              "lassoPoints" in evt
                ? (evt.lassoPoints as { x?: unknown[]; y?: unknown[] })
                : undefined,
          }));
        })}
        className="w-full"
        useResizeHandler={true}
        frames={figure.frames ?? undefined}
        onError={useEvent((err: Error) => {
          Logger.error("PlotlyPlugin: ", err);
        })}
      />
    );
  },
);
PlotlyComponent.displayName = "PlotlyComponent";

/**
 * This is a hack to extract the points with their original keys,
 * instead of the ones that Plotly uses internally,
 * by using the hovertemplate.
 */
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
];

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
  const traceX = trace.x;
  const traceY = trace.y;

  const getIndexedValue = (series: unknown, idx: number): unknown => {
    if (Array.isArray(series) || ArrayBuffer.isView(series)) {
      return (series as ArrayLike<unknown>)[idx];
    }
    if (typeof series === "object" && series !== null && "length" in series) {
      const maybeLength = Number(
        (series as { length?: unknown }).length ?? Number.NaN,
      );
      if (Number.isFinite(maybeLength) && idx >= 0 && idx < maybeLength) {
        return (series as Record<number, unknown>)[idx];
      }
    }
    return undefined;
  };

  if (nextFields.x === undefined) {
    const inferredX = getIndexedValue(traceX, pointIndex);
    if (inferredX !== undefined) {
      nextFields.x = inferredX;
    }
  }
  if (nextFields.y === undefined) {
    const inferredY = getIndexedValue(traceY, pointIndex);
    if (inferredY !== undefined) {
      nextFields.y = inferredY;
    }
  }

  return nextFields;
}

export function extractPoints(
  points: Plotly.PlotDatum[],
): Record<AxisName, AxisDatum>[] {
  if (!points) {
    return [];
  }

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
