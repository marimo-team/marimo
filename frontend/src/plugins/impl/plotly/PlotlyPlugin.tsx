/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";

import { IPlugin, IPluginProps } from "@/plugins/types";

import type { Figure } from "react-plotly.js";
import { Logger } from "@/utils/Logger";

import "./plotly.css";
import "./mapbox.css";
import { lazy, memo, useMemo } from "react";
import useEvent from "react-use-event-hook";
import { PlotlyTemplateParser, createParser } from "./parse-from-template";

interface Data {
  figure: Figure;
}

type AxisName = string;
type AxisDatum = unknown;

type T =
  | {
      points?: Array<Record<AxisName, AxisDatum>>;
      indices?: number[];
      range?: {
        x?: number[];
        y?: number[];
      };
    }
  | undefined;

export class PlotlyPlugin implements IPlugin<T, Data> {
  tagName = "marimo-plotly";

  validator = z.object({
    figure: z
      .object({})
      .passthrough()
      .transform((spec) => spec as unknown as Figure),
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
  setValue: (value: T) => void;
  host: HTMLElement;
}

const config = {
  displaylogo: false,
};

export const LazyPlot = lazy(() => import("react-plotly.js"));

export const PlotlyComponent = memo(
  ({ figure, setValue }: PlotlyPluginProps) => {
    const layout: Partial<Plotly.Layout> = useMemo(() => {
      // Enable autosize if width is not specified
      const shouldAutoSize = figure.layout.width === undefined;
      return {
        autosize: shouldAutoSize,
        dragmode: "select",
        height: 540,
        // Prioritize user's config
        ...figure.layout,
      };
    }, [figure.layout]);

    return (
      <LazyPlot
        {...figure}
        layout={layout}
        config={config}
        onSelected={useEvent((evt: Readonly<Plotly.PlotSelectionEvent>) => {
          if (!evt) {
            return;
          }

          setValue({
            points: extractPoints(evt.points),
            indices: evt.points.map((point) => point.pointIndex),
            range: evt.range,
          });
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
