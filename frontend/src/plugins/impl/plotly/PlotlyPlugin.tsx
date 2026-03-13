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

export const PlotlyComponent = memo(
  ({ figure: originalFigure, value, setValue, config }: PlotlyPluginProps) => {
    // Used for rendering LaTeX. TODO: Serve this library from Marimo
    const scriptStatus = useScript(
      "https://cdn.jsdelivr.net/npm/mathjax-full@3.2.2/es5/tex-mml-svg.min.js",
    );
    const isScriptLoaded = scriptStatus === "ready";

    const { figure, layout, handleReset } = usePlotlyLayout({
      originalFigure,
      initialValue: value,
      isScriptLoaded,
    });

    const handleResetWithClear = useEvent(() => {
      handleReset();
      setValue({});
    });

    const configMemo = useDeepCompareMemoize(config);
    const plotlyConfig = useMemo((): Partial<Plotly.Config> => {
      return {
        displaylogo: false,
        modeBarButtonsToAdd: [
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
        ],
        // Prioritize user's config
        ...configMemo,
      };
    }, [handleResetWithClear, configMemo]);

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
          // Only handle clicks for chart types where box/lasso selection
          // (onSelected) doesn't work, such as heatmaps.
          const isHeatmap = evt.points.some(
            (point) => point.data?.type === "heatmap",
          );
          if (!isHeatmap) {
            return;
          }
          setValue((prev) => ({
            ...prev,
            points: extractPoints(evt.points),
            indices: evt.points.map((point) => point.pointIndex),
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
            indices: evt.points.map((point) => point.pointIndex),
            range: evt.range,
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
  "pointIndex",
];

function extractPoints(
  points: Plotly.PlotDatum[],
): Record<AxisName, AxisDatum>[] {
  if (!points) {
    return [];
  }

  let parser: PlotlyTemplateParser | undefined;

  return points.map((point) => {
    // Get the first hovertemplate
    const hovertemplate = Array.isArray(point.data.hovertemplate)
      ? point.data.hovertemplate[0]
      : point.data.hovertemplate;

    // For chart types with standard point keys (e.g. heatmaps),
    // or when there's no hovertemplate, pick keys directly from the point.
    if (!hovertemplate || point.data?.type === "heatmap") {
      return pick(point, STANDARD_POINT_KEYS);
    }

    // Update or create a parser
    parser = parser
      ? parser.update(hovertemplate)
      : createParser(hovertemplate);
    return parser.parse(point);
  });
}
