/* Copyright 2024 Marimo. All rights reserved. */

import type { Figure } from "react-plotly.js";
import { z } from "zod";
import type { IPlugin, IPluginProps, Setter } from "@/plugins/types";
import { Logger } from "@/utils/Logger";

import "./plotly.css";
import "./mapbox.css";
import { usePrevious } from "@uidotdev/usehooks";
import { isEqual, pick, set } from "lodash-es";
import { type JSX, lazy, memo, useEffect, useMemo, useState } from "react";
import useEvent from "react-use-event-hook";
import { useDeepCompareMemoize } from "@/hooks/useDeepCompareMemoize";
import { useScript } from "@/hooks/useScript";
import { Arrays } from "@/utils/arrays";
import { Objects } from "@/utils/objects";
import { createParser, type PlotlyTemplateParser } from "./parse-from-template";

interface Data {
  figure: Figure;
  config: Partial<Plotly.Config>;
}

type AxisName = string;
type AxisDatum = unknown;

type T =
  | {
      points?: Array<Record<AxisName, AxisDatum>> | Plotly.PlotDatum[];
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

export const LazyPlot = lazy(() => import("react-plotly.js"));

function initialLayout(figure: Figure): Partial<Plotly.Layout> {
  // Enable autosize if width is not specified
  const shouldAutoSize = figure.layout.width === undefined;
  return {
    autosize: shouldAutoSize,
    dragmode: "select",
    height: 540,
    // Prioritize user's config
    ...figure.layout,
  };
}

const SUNBURST_DATA_KEYS: Array<keyof Plotly.SunburstPlotDatum> = [
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
    const [figure, setFigure] = useState(() => {
      // We clone the figure since Plotly mutates the figure in place
      return structuredClone(originalFigure);
    });

    // Used for rendering LaTeX. TODO: Serve this library from Marimo
    const scriptStatus = useScript(
      "https://cdn.jsdelivr.net/npm/mathjax-full@3.2.2/es5/tex-mml-svg.min.js",
    );
    const isScriptLoaded = scriptStatus === "ready";

    useEffect(() => {
      const nextFigure = structuredClone(originalFigure);
      setFigure(nextFigure);
      setLayout((prev) => ({
        ...initialLayout(nextFigure),
        ...prev,
      }));
    }, [originalFigure, isScriptLoaded]);

    const [layout, setLayout] = useState<Partial<Plotly.Layout>>(() => {
      return {
        ...initialLayout(figure),
        // Override with persisted values (dragmode, xaxis, yaxis)
        ...value,
      };
    });

    const handleReset = useEvent(() => {
      const nextFigure = structuredClone(originalFigure);
      setFigure(nextFigure);
      setLayout(initialLayout(nextFigure));
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
            click: handleReset,
          },
        ],
        // Prioritize user's config
        ...configMemo,
      };
    }, [handleReset, configMemo]);

    const prevFigure = usePrevious(figure) ?? figure;

    useEffect(() => {
      const omitKeys = new Set<keyof Plotly.Layout>([
        "autosize",
        "dragmode",
        "xaxis",
        "yaxis",
      ]);

      // If the key was updated externally (e.g. can be specifically passed in the config)
      // then we need to update the layout
      for (const key of omitKeys) {
        if (!isEqual(figure.layout[key], prevFigure.layout[key])) {
          omitKeys.delete(key);
        }
      }

      // Update layout when figure.layout changes
      // Omit keys that we don't want to override
      const layout = Objects.omit(figure.layout, omitKeys);
      setLayout((prev) => ({ ...prev, ...layout }));
    }, [figure.layout, prevFigure.layout]);

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
        // @ts-expect-error We patched this prop here so it doesn't exist in the types
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
        onRestyle={useEvent((data: Readonly<Plotly.PlotRestyleEvent>) => {
          if (!data) {
            return;
          }

          const [update, traceIndices] = data;

          // If there are no constraints, it's a reset
          if (!("constraints" in update)) {
            setValue({});
            return;
          }

          const constraints = update.constraints;
          if (constraints) {
            const ranges = Object.fromEntries(
              Object.entries(constraints).map(([key, value]) => {
                const label = (originalFigure.data[traceIndices[0]] as any).dimensions[key].label;
                return [label, value.range];
              })
            );
            setValue({ ranges });
          }
        })}
        config={plotlyConfig}
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
        onError={useEvent((err) => {
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
function extractPoints(
  points: Plotly.PlotDatum[],
): Array<Record<AxisName, AxisDatum>> {
  if (!points) {
    return [];
  }

  let parser: PlotlyTemplateParser | undefined;

  return points.map((point) => {
    // Get the first hovertemplate
    const hovertemplate = Array.isArray(point.data.hovertemplate)
      ? point.data.hovertemplate[0]
      : point.data.hovertemplate;
    // Update or create a parser
    parser = parser
      ? parser.update(hovertemplate)
      : createParser(hovertemplate);
    return parser.parse(point);
  });
}
